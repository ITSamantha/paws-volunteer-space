class DeliveryError(Exception):
    """Сообщение не доставлено.

    retryable=False — повторять бессмысленно (пользователь заблокировал бота, чат не найден).
    retry_after — сколько секунд просит подождать Telegram; без него задержку выбирает очередь.
    """

    def __init__(self, message: str, retryable: bool = True, retry_after: float | None = None):
        """Запоминает, можно ли повторить попытку и когда."""
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after
