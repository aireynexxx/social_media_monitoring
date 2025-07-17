import subprocess

def generate_report():
    with open("reports/prompt.txt", "r", encoding="utf-8") as f:
        prompt = f.read()


    result = subprocess.run(
        'type prompt.txt | ollama run llama3.1:8b',
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8"
    )

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    if stdout:
        print("\n=== Russian Mood Report ===\n")
        print(stdout)
        with open("reports/mood_report.md", "w", encoding="utf-8") as f:
            f.write(stdout)
    else:
        print("\n No output from Ollama.")

    if stderr:
        print("\n=== ️ STDERR from Ollama ===\n")
        print(stderr)
