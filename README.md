# Онлайн-голосование с номинациями

Система для проведения онлайн-голосования с поддержкой номинаций, кандидатов и голосования.

## Основные функции

- Управление номинациями (создание, редактирование, удаление)
- Управление кандидатами (добавление, редактирование, удаление)
- Голосование за кандидатов
- Просмотр статистики голосования
- Аутентификация через Google OAuth2
- История изменений объектов
- Экспорт данных в Excel
- Периодические задачи (ежедневная статистика, автоматическое закрытие номинаций)

## Полезные команды (Docker, Ruff, Git)
```bash
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
docker-compose ps
docker-compose exec web python manage.py seed --clear
docker-compose exec web python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.create_superuser('admin', 'admin@example.com', 'admin123')"
docker-compose exec web celery -A config worker --loglevel=info
ruff check . --fix
ruff check . 
ruff format .
git add .
docker-compose logs celery
docker-compose exec web python manage.py test
```

### Локальный запуск (без Docker)

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```