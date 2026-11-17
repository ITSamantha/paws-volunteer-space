# Уведомления
notification-registration-confirmed = Вы записаны на «{ $title }»{ $when }. Если планы изменятся, отмените запись.
notification-registration-pending = Заявка на «{ $title }» отправлена организатору. Мы сообщим о решении.
notification-registration-approved = Организатор одобрил вашу заявку на «{ $title }»{ $when }. Вы записаны.
notification-registration-rejected = К сожалению, заявка на «{ $title }» отклонена. Причина: { $reason }.
notification-registration-waitlisted = На «{ $title }» пока нет свободных мест, вы в листе ожидания. Если место освободится, мы сообщим.
notification-spot-freed = На «{ $title }» освободилось место! Откройте мероприятие и займите его, пока это не сделал кто-то другой.
notification-registration-cancelled = Ваша запись на «{ $title }» отменена.
notification-event-changed = В «{ $title }» есть изменения: { $changes }.
notification-event-cancelled = Мероприятие «{ $title }»{ $when } отменено. Причина: { $reason }.
notification-reminder = Напоминаем: «{ $title }»{ $when }. Ждём вас!
notification-new-event = Новое мероприятие: «{ $title }»{ $when }. Откройте список и запишитесь.
notification-organizer-new-registration = Новая запись на «{ $title }»: { $person }.
notification-organizer-approval-requested = Заявка на «{ $title }» от { $person } ждёт вашего решения.
notification-organizer-cancellation = { $person } отменил(а) запись на «{ $title }». Причина: { $reason }.
notification-user-blocked = Ваш доступ ограничен. Причина: { $reason }.
notification-broadcast = { $text }

# Части сообщений
time-suffix = { " " }({ $moment })
fallback-title = мероприятие
fallback-reason = не указана
fallback-person = волонтёр
fallback-changes = уточните детали в карточке
field-starts-at = время начала
field-ends-at = время окончания
field-location = место встречи
field-shelter-id = приют
field-instructions = что взять с собой

# Команды
start-greeting =
    Привет! Я бот клуба «Лапки помощи».

    Здесь можно посмотреть выезды, записаться и получить напоминание. Выберите, что открыть.
menu-events = 🐾 Мероприятия
menu-mine = 💛 Мои записи
menu-organizer = 🗂 Для организаторов
menu-soon = Этот раздел ещё готовится. Скоро здесь можно будет всё сделать.
menu-back = ← В меню
events-to-list = ← К списку
events-join = 💛 Записаться
events-joined-registered = Вы записаны. Если планы изменятся, запись можно будет отменить.
events-joined-pending = Заявка отправлена. Напишем, когда организатор решит.
events-joined-waitlisted = Мест пока нет, вы в листе ожидания. Если место освободится, мы напишем.
events-already = Вы уже записаны на этот выезд.
events-title = Куда можно поехать. Нажмите на выезд, чтобы открыть его.
events-empty = Пока нет предстоящих выездов. Когда появится новый, мы напишем.
events-unavailable = Не получилось открыть. Попробуйте ещё раз чуть позже.
events-place-unknown = место уточним
events-card =
    🐾 { $title }
    Когда: { $when }
    Где: { $place }
    Свободно мест: { $free } из { $capacity }
    { $details }
