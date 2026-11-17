# Notifications
notification-registration-confirmed = You are registered for “{ $title }”{ $when }. If your plans change, please cancel your registration.
notification-registration-pending = Your request for “{ $title }” has been sent to the organizer. We will let you know their decision.
notification-registration-approved = The organizer approved your request for “{ $title }”{ $when }. You are registered.
notification-registration-rejected = Unfortunately, your request for “{ $title }” was declined. Reason: { $reason }.
notification-registration-waitlisted = There are no free spots left for “{ $title }”, so you are on the waiting list. We will let you know if a spot opens up.
notification-spot-freed = A spot has opened up for “{ $title }”! Open the event and take it before someone else does.
notification-registration-cancelled = Your registration for “{ $title }” has been cancelled.
notification-event-changed = “{ $title }” has changed: { $changes }.
notification-event-cancelled = The event “{ $title }”{ $when } has been cancelled. Reason: { $reason }.
notification-reminder = Reminder: “{ $title }”{ $when }. See you there!
notification-new-event = A new event: “{ $title }”{ $when }. Open the list and sign up.
notification-organizer-new-registration = New registration for “{ $title }”: { $person }.
notification-organizer-approval-requested = A request for “{ $title }” from { $person } is waiting for your decision.
notification-organizer-cancellation = { $person } cancelled their registration for “{ $title }”. Reason: { $reason }.
notification-user-blocked = Your access has been restricted. Reason: { $reason }.
notification-broadcast = { $text }

# Message parts
time-suffix = { " " }({ $moment })
fallback-title = the event
fallback-reason = not specified
fallback-person = a volunteer
fallback-changes = check the details on the event page
field-starts-at = start time
field-ends-at = end time
field-location = meeting point
field-shelter-id = shelter
field-instructions = what to bring

# Commands
start-greeting =
    Hi! I'm the bot of the “Helping Paws” club.

    Here you can see visits, sign up, and get a reminder. Choose what to open.
menu-events = 🐾 Events
menu-mine = 💛 My registrations
menu-organizer = 🗂 For organizers
menu-soon = This part is still being prepared. You will be able to use it soon.
menu-back = ← Back to menu
events-to-list = ← Back to the list
events-join = 💛 Sign up
events-joined-registered = You are signed up. You will be able to cancel if your plans change.
events-joined-pending = Your request is sent. We will write when the organizer decides.
events-joined-waitlisted = There is no place yet, so you are on the waiting list. We will write if one opens.
events-already = You are already signed up for this visit.
mine-title = Your registrations
mine-empty = You have not signed up yet. Open events and choose a visit.
mine-line = 🐾 { $title }, { $when } — { $status }
status-registered = you are signed up
status-pending = waiting for a decision
status-waitlisted = you are on the waiting list
status-rejected = the request was declined
status-cancelled = the registration was cancelled
status-attended = you were there
status-absent = you were absent
events-title = Where you can go. Tap a visit to open it.
events-empty = There are no upcoming visits yet. We will write when a new one appears.
events-unavailable = This could not be opened. Please try again in a moment.
events-place-unknown = the meeting place will be confirmed
events-card =
    🐾 { $title }
    When: { $when }
    Where: { $place }
    Free places: { $free } of { $capacity }
    { $details }
