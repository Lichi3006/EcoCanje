import os
import time
from cassandra.cluster import Cluster

db_clients = {}

_CASSANDRA_CONNECT_TIMEOUT    = 3   # segundos por intento
_CASSANDRA_MAX_REINTENTOS     = 3   # intentos al reconectar (post-Docker-restart)
_CASSANDRA_PAUSA_REINTENTOS   = 1   # segundos entre reintentos
_CASSANDRA_TIMEOUT_INICIAL    = 3   # timeout del primer intento (falla rapida si todo esta caido)


def _crear_sesion_cassandra():
    """
    Crea una sesión de Cassandra desde cero, cerrando el cluster previo si existe.
    Reintenta hasta _CASSANDRA_MAX_REINTENTOS veces con pausa entre ellos para
    tolerar el período de inicialización de la JVM de Cassandra tras un restart
    de Docker (que típicamente tarda entre 40 y 60 segundos).
    """
    # Cerramos el cluster viejo para liberar recursos
    cluster_viejo = db_clients.get("cassandra_cluster")
    if cluster_viejo:
        try:
            cluster_viejo.shutdown()
        except Exception:
            pass

    cassandra_hosts = os.getenv("CASSANDRA_HOSTS", "cassandra").split(",")
    ultimo_error = None

    for intento in range(1, _CASSANDRA_MAX_REINTENTOS + 1):
        try:
            print(f"[SISTEMA] Intento {intento}/{_CASSANDRA_MAX_REINTENTOS} de conexion a Cassandra ({cassandra_hosts})...")
            cluster_nuevo = Cluster(
                contact_points=cassandra_hosts,
                connect_timeout=_CASSANDRA_CONNECT_TIMEOUT,
                control_connection_timeout=_CASSANDRA_CONNECT_TIMEOUT,
            )
            session = cluster_nuevo.connect()
            session.set_keyspace("ecocanje_ks")
            db_clients["cassandra_cluster"] = cluster_nuevo
            db_clients["cassandra_session"] = session
            print(f"[SISTEMA] Sesion de Cassandra establecida exitosamente en el intento {intento}.")
            return session
        except Exception as e:
            ultimo_error = e
            print(f"[SISTEMA] Intento {intento} fallido: {e}")
            if intento < _CASSANDRA_MAX_REINTENTOS:
                time.sleep(_CASSANDRA_PAUSA_REINTENTOS)

    # Si llegamos acá, agotamos todos los intentos
    db_clients["cassandra_session"] = None
    raise ConnectionError(
        f"Cassandra no disponible tras {_CASSANDRA_MAX_REINTENTOS} intentos. "
        f"Puede estar inicializando su JVM (esperar 60 segundos) o estar caida. "
        f"Ultimo error: {ultimo_error}"
    )



def get_cassandra_session(reconectar=False):
    """
    Retorna la sesion activa de Cassandra implementando Reconexion Perezosa (Lazy Reconnect).

    Flujo de decision:
    - Si no hay sesion previa (primer arranque o todo caido): intenta UNA vez con timeout corto.
      Falla rapido para no bloquear el panel cuando todo esta caido.
    - Si hay sesion en apariencia valida: la verifica con ping liviano.
    - Si el ping falla (post-restart de Docker): reintenta hasta 3 veces con pausa,
      porque la JVM de Cassandra puede tardar en inicializar.
    """
    session = db_clients.get("cassandra_session")

    # Caso 1: no hay sesion previa (todo caido o primer arranque)
    # Hacemos UN solo intento rapido para no bloquear el usuario.
    if session is None or getattr(session, "is_shutdown", True):
        cluster_viejo = db_clients.get("cassandra_cluster")
        if cluster_viejo:
            try:
                cluster_viejo.shutdown()
            except Exception:
                pass

        cassandra_hosts = os.getenv("CASSANDRA_HOSTS", "cassandra").split(",")
        try:
            print(f"[SISTEMA] Intento inicial de conexion a Cassandra ({cassandra_hosts})...")
            cluster_nuevo = Cluster(
                contact_points=cassandra_hosts,
                connect_timeout=_CASSANDRA_TIMEOUT_INICIAL,
                control_connection_timeout=_CASSANDRA_TIMEOUT_INICIAL,
            )
            nueva_session = cluster_nuevo.connect()
            nueva_session.set_keyspace("ecocanje_ks")
            db_clients["cassandra_cluster"] = cluster_nuevo
            db_clients["cassandra_session"] = nueva_session
            print("[SISTEMA] Sesion de Cassandra establecida exitosamente.")
            return nueva_session
        except Exception as e:
            db_clients["cassandra_session"] = None
            raise ConnectionError(f"Cassandra no disponible: {type(e).__name__}. Verificar que el contenedor este activo.")

    # Caso 2: hay sesion en memoria. La verificamos con ping liviano.
    try:
        session.execute("SELECT now() FROM system.local")
        return session
    except Exception:
        print("[SISTEMA] Ping a Cassandra fallo. Iniciando reconexion con reintentos (post-restart de Docker)...")
        db_clients["cassandra_session"] = None
        return _crear_sesion_cassandra()

