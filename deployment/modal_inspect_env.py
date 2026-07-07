import modal
import os

app = modal.App("smc-alpha-environ")
volume = modal.Volume.from_name("smc-alpha-storage", create_if_missing=False)

@app.function(
    image=modal.Image.debian_slim(),
    secrets=[modal.Secret.from_name("smc-secrets")],
    timeout=600
)
def check_environ():
    print("Environment variables keys:")
    for key in sorted(os.environ.keys()):
        # Hide value to be safe, just print length
        val = os.environ[key]
        print(f"  {key}: length={len(val)}")
