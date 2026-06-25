import argparse
import requests
from typing import Optional, Tuple
import tkinter as tk
from tkinter import ttk, messagebox
import threading

# Попытка импортировать красивые темы, если нет - используем стандартную
try:
    from ttkthemes import ThemedTk
    USE_THEMES = True
except ImportError:
    USE_THEMES = False

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"

def get_coordinates(city: str) -> Optional[Tuple[float, float]]:
    params = {"name": city, "count": 1, "language": "en", "format": "json"}
    try:
        resp = requests.get(GEO_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return None
        r = results[0]
        return r["latitude"], r["longitude"]
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при поиске координат: {e}")
        return None

def fetch_weather(latitude: float, longitude: float) -> dict:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current_weather": True,
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "auto",
        "forecast_days": 3,
    }
    resp = requests.get(OPEN_METEO_URL, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()

def format_output(city: str, data: dict) -> str:
    current = data["current_weather"]
    temp = current["temperature"]
    windspeed = current["windspeed"]
    winddir = current["winddirection"]

    # Формируем красивый заголовок с эмодзи
    lines = [
        f"Погода в {city}:",
        "",
        f"🔥 Текущая температура: {temp} °C",
        f"💨 Скорость ветра: {windspeed} км/ч",
        f"Направление ветра: {winddir}°",
        "",
        "Прогноз на ближайшие дни:"
    ]

    daily = data.get("daily", {})
    dates = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])

    count = min(len(dates), len(max_temps), len(min_temps))
    for i in range(count):
        # Делаем даты чуть более читаемыми (берем только часть строки, если нужно)
        date_str = dates[i]
        lines.append(f"   • {date_str}: ☀️ {max_temps[i]}°C | ❄️ {min_temps[i]}°C")

    return "\n".join(lines)

class WeatherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Прогноз Погоды")
        self.root.geometry("550x450")
        
        # Настройка стилей
        style = ttk.Style()
        # Используем современную тему, если доступна
        if USE_THEMES:
            self.root.set_theme("clam") 
        else:
            style.theme_use("alt") # Чуть лучше стандартного 'default'

        # Конфигурация шрифтов
        font_main = ("Segoe UI", 11)
        font_header = ("Segoe UI", 14, "bold")
        font_large = ("Segoe UI", 20, "bold")

        # Основной фрейм с отступами для красоты
        main_frame = ttk.Frame(root, padding=20)
        main_frame.pack(fill="both", expand=True)

        # Заголовок
        self.lbl_title = ttk.Label(main_frame, text="ваш прогноз погоды", font=font_header)
        self.lbl_title.pack(pady=(0, 20))

        # Поле ввода города
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill="x", pady=(0, 15))
        
        self.city_label = ttk.Label(input_frame, text="Город:", font=font_main)
        self.city_label.pack(side="left", padx=(0, 10))

        self.city_entry = ttk.Entry(input_frame, width=30, font=font_main)
        self.city_entry.pack(side="left", fill="x", expand=True)
        self.city_entry.bind("<Return>", lambda e: self.start_fetch_thread())
        self.city_entry.focus_set() # Автофокус

        # Кнопка
        self.btn = ttk.Button(main_frame, text="Показать погоду", command=self.start_fetch_thread, style="Accent.TButton")
        # Accent стиль работает в новых версиях ttk, если нет - просто кнопка
        try:
            self.btn.pack(pady=10, ipadx=20, ipady=5)
        except:
            self.btn.pack(pady=10)

        # Область вывода (текстовая область с прокруткой)
        output_frame = ttk.LabelFrame(main_frame, text="Результат", padding=10)
        output_frame.pack(fill="both", expand=True)

        self.output_text = tk.Text(output_frame, wrap="word", state="disabled", height=12, font=("Consolas", 11), bg="#f0f0f0")
        scrollbar = ttk.Scrollbar(output_frame, orient="vertical", command=self.output_text.yview)
        self.output_text.configure(yscrollcommand=scrollbar.set)

        self.output_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def start_fetch_thread(self):
        """Запускает запрос в отдельном потоке, чтобы не морозить интерфейс"""
        city = self.city_entry.get().strip()
        if not city:
            messagebox.showwarning("Внимание", "Пожалуйста, введите название города.")
            return

        # Блокируем ввод и меняем текст кнопки
        self.city_entry.config(state="disabled")
        self.btn.config(text="Загрузка...", state="disabled")
        self.set_output("ожидание данных от сервера...")

        # Создаем поток
        thread = threading.Thread(target=self.fetch_weather_thread, args=(city,), daemon=True)
        thread.start()

    def fetch_weather_thread(self, city: str):
        """Функция, которая выполняется в фоне"""
        coords = get_coordinates(city)
        
        def update_ui_with_result(result_text, error=False):
            """Безопасное обновление интерфейса из потока"""
            self.city_entry.config(state="normal")
            if error:
                self.btn.config(text="Показать погоду")
                self.set_output(result_text)
            else:
                self.btn.config(text="Обновить")
                self.set_output(result_text)

        if not coords:
            update_ui_with_result(f"❌ Город '{city}' не найден. Проверьте написание.", error=True)
            return

        lat, lon = coords
        try:
            data = fetch_weather(lat, lon)
            text = format_output(city, data)
            update_ui_with_result(text)
        except requests.exceptions.Timeout:
            update_ui_with_result("❌ Ошибка: Превышено время ожидания ответа сервера.", error=True)
        except requests.exceptions.RequestException as e:
            update_ui_with_result(f"❌ Ошибка соединения: {str(e)}", error=True)
        except Exception as e:
            update_ui_with_result(f"❌ Произошла непредвиденная ошибка: {str(e)}", error=True)

    def set_output(self, text: str):
        self.output_text.config(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", text)
        self.output_text.config(state="disabled")

def main():
    if USE_THEMES:
        root = ThemedTk()
    else:
        root = tk.Tk()
        
    app = WeatherApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
