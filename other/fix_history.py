import json
import os

FILE = "history.json"

if os.path.exists(FILE):
    with open(FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print("❌ history.json повреждён, создаю новый")
            data = []

    fixed = []
    for item in data:
        clean = {}
        for k, v in item.items():
            ck = k.strip()
            if isinstance(v, list):
                clean[ck] = [str(x).strip() for x in v if x]
            elif isinstance(v, str):
                clean[ck] = v.strip()
            else:
                clean[ck] = v
        fixed.append(clean)

    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(fixed, f, indent=2, ensure_ascii=False)
    print(f"✅ Исправлено {len(fixed)} записей в {FILE}")
else:
    print("⚠️ history.json не найден — будет создан автоматически при первом событии")
