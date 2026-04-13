import psycopg2

URL  = "aws-1-us-east-1.pooler.supabase.com"
USER = "postgres.tsfzwlmudywaixrltjuk"
PASS = "mM1i8nSykz2yJ47H"
DB   = "postgres"
PORT = 6543

def get_conexion():
    try:
        con = psycopg2.connect(
            host=URL,
            user=USER,
            password=PASS,
            dbname=DB,
            port=PORT
        )
        print(">>> [Atlas] Conexión establecida con el tatami en la nube.")
        return con
    except Exception as e:
        print(f">>> [Error] Falló la conexión: {e}")
        return None