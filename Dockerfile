FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY food_saver.py ./
EXPOSE 5000
ENV FLASK_RUN_PORT=5000
CMD ["python", "food_saver.py"]
