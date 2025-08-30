# Food Saver 🥕🥦🥩

**Food Saver** is a lightweight, open‑source web app that helps reduce food waste by tracking your fridge and pantry items. You can add groceries, set expiry dates, and get notified before food spoils.

🌍 Built with sustainability in mind, Food Saver encourages mindful consumption and reduces unnecessary waste.

---

## ✨ Features

* Add items with quantity, category, and expiry date
* View upcoming expiring items
* Notifications for food nearing expiry
* Runs locally with SQLite — no external services needed
* Simple Flask web app — deploy anywhere
* Docker support for easy deployment
* CI/CD ready with GitHub Actions

---

## 🚀 Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/jeffreycyr/Food-Saver.git
cd Food-Saver
```

### 2. Create a virtual environment & install dependencies

```bash
python3 -m venv venv
source venv/bin/activate   # (on Linux/Mac)
venv\Scripts\activate      # (on Windows)

pip install -r requirements.txt
```

### 3. Run the app

```bash
python food_saver.py
```

Visit `http://127.0.0.1:5000` in your browser 🎉

---

## 🐳 Run with Docker

```bash
docker build -t food-saver .
docker run -p 5000:5000 food-saver
```

---

## 📂 Project Structure

```
Food-Saver/
├── food_saver.py        # Main Flask app
├── requirements.txt     # Python dependencies
├── Dockerfile           # Container setup
├── .gitignore
├── LICENSE
├── CONTRIBUTING.md
├── CHANGELOG.md
└── README.md            # This file
```

---

## 🛠️ Tech Stack

* **Backend**: Python, Flask
* **Database**: SQLite (lightweight, file‑based)
* **Deployment**: Docker, GitHub Actions

---

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md).

Ways you can help:

* Add categories for common food types
* Improve the UI (Bootstrap/Tailwind)
* Add user authentication
* Extend notifications (e.g., email, SMS)

---

## 📜 License

MIT License — see [LICENSE](LICENSE).

---

## ⭐ Acknowledgments

This project was bootstrapped with the help of **ChatGPT (OpenAI)** and launched by [@jeffreycyr](https://github.com/jeffreycyr).
