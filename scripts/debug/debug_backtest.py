import modal
from database import get_db_connection

image = (
    modal.Image.debian_slim()
    .add_local_python_source("config")
    .add_local_python_source("database")
)

app = modal.App("smc-debug")
volume = modal.Volume.from_name("smc-alpha-storage")

@app.function(image=image, volumes={"/data": volume})
def check_results():
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT count(*) FROM backtest_results")
        count = c.fetchone()[0]
        print(f"📉 Rows in backtest_results: {count}")
        
        if count > 0:
            c.execute("SELECT * FROM backtest_results ORDER BY id DESC LIMIT 1")
            row = dict(c.fetchone())
            print(f"Latest Result: {row}")
    except Exception as e:
        print(f"Error querying DB: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    with app.run():
        check_results.call()
