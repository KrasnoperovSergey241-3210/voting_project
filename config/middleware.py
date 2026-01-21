class SimpleDebugMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        print(f"→ Запрос пришёл: {request.method} {request.path}")

        response = self.get_response(request)

        print(f"← Ответ ушёл со статусом: {response.status_code}")

        return response
