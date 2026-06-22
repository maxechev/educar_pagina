with open("respaldo.json", "r", encoding="utf-16") as f:
    data = f.read()

with open("respaldo_utf8.json", "w", encoding="utf-8") as f:
    f.write(data)