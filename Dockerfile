# Use Python 3.11
FROM python:3.11-slim


# Set work directory
WORKDIR /app


# Copy project files
COPY . .


# Install dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt


# Run bot
CMD ["python", "bot.py"]