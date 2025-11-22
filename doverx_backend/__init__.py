import os

if os.getenv("USE_PYMYSQL", "True") == "True":
    try:
        import pymysql
        pymysql.install_as_MySQLdb()
    except Exception:
        pass