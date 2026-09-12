import re

with open("/Users/nicholasmacaskill/Desktop/bayesian_pivot_codebase_mix_v3.txt", "r") as f:
    content = f.read()

# Extract tl_client.py
start_marker = "FILE: src/clients/tl_client.py\n================================================================================\n"
start_idx = content.find(start_marker) + len(start_marker)
end_idx = content.find("================================================================================", start_idx)
# Need to go back 2 newlines before the next marker
tl_content = content[start_idx:end_idx].strip() + "\n"

with open("src/clients/tl_client.py", "w") as f:
    f.write(tl_content)

print("Restored tl_client.py")
