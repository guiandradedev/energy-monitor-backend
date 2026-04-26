from sqlalchemy import create_engine, text

engine = create_engine("postgresql+psycopg2://postgres:senha123@localhost/postgres")

# query = """
# SELECT created_at, device_id, rms_sct1, rms_sct2, rms_zmpt1, rms_zmpt2
# FROM breaker
# WHERE created_at >= NOW() - INTERVAL '24 hours'
# ORDER BY created_at DESC;
# """


# with engine.connect() as conn:
#     result = conn.execute(text(query))
#     for row in result:
#         print(row)