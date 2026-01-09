
import modal

app = modal.App("test-hello")

@app.function()
def hello():
    print("HELLO FROM MODAL")
    return "SUCCESS"

if __name__ == "__main__":
    with app.run():
        print(hello.remote())
