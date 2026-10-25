# Telegram translation review (E1b)

All rows are application UI copy. Source titles, diagnostic exceptions, IDs and URLs are not translated.
The disabled-platform /start copy is corrected to describe YouTube only; enabled-platform branches retain the same message counts.
No upload confirmation, retry, selection or resource-policy meaning is changed. Item numbers mean original source positions.

| EN source | RU | ES | Context / constraint |
|---|---|---|---|
| Hi! Send a YouTube link to download an individual video or audio. Instagram and TikTok downloads aren't enabled here. | Привет! Отправь ссылку на отдельное видео YouTube, чтобы скачать видео или аудио. Загрузка из Instagram и TikTok здесь не включена. | ¡Hola! Envía un enlace de YouTube para descargar un vídeo individual o su audio. Las descargas de Instagram y TikTok no están activadas aquí. | handlers |
| This choice is no longer available. Send the link again. | Выбор больше недоступен. Отправь ссылку ещё раз. | Esta opción ya no está disponible. Envía el enlace de nuevo. | handlers |
| Couldn't process this choice. Send the link again. | Не удалось обработать выбор. Отправь ссылку ещё раз. | No se pudo procesar esta opción. Envía el enlace de nuevo. | handlers |
| No safe download option is available for this link. | Для этой ссылки нет безопасного варианта скачивания. | No hay una opción de descarga segura para este enlace. | handlers |
| 🎬 Video | 🎬 Видео | 🎬 Vídeo | handlers |
| 🎵 Audio | 🎵 Аудио | 🎵 Audio | handlers |
| Low | Низкое | Baja | handlers |
| Medium | Среднее | Media | handlers |
| High | Высокое | Alta | handlers |
| Couldn't process this link. Check it and try again. | Не удалось обработать эту ссылку. Проверь её и попробуй ещё раз. | No se pudo procesar este enlace. Revísalo e inténtalo de nuevo. | handlers |
| YouTube processing is busy or temporarily unavailable. Try again later. | Сейчас обработка YouTube занята или временно недоступна. Попробуй чуть позже. | El procesamiento de YouTube está ocupado o temporalmente no disponible. Inténtalo más tarde. | handlers |
| Couldn't get video information. The video may be deleted, private or unavailable. | Не удалось получить данные видео. Возможно, оно удалено, закрыто или недоступно. | No se pudo obtener la información del vídeo. Puede haberse eliminado, ser privado o no estar disponible. | handlers |
| The video download is incomplete or couldn't be processed. Try another link. | Видео скачано не полностью или не удалось обработать. Попробуй другую ссылку. | La descarga del vídeo está incompleta o no se pudo procesar. Prueba con otro enlace. | handlers |
| Couldn't download the video. Try again later. | Не удалось скачать видео. Попробуй ещё раз позже. | No se pudo descargar el vídeo. Inténtalo más tarde. | handlers |
| Downloads from this platform aren't enabled yet. | Скачивание с этой платформы пока не подключено. | Las descargas de esta plataforma aún no están activadas. | handlers |
| This request is already being processed. | Запрос уже обрабатывается. | Esta solicitud ya se está procesando. | handlers |
| Choose a format: | Выбери формат: | Elige el formato: | handlers |
| Choose the quality: | Выбери качество: | Elige la calidad: | handlers |
| Couldn't recognize the link. Send a full HTTP or HTTPS link to YouTube, Instagram or TikTok. | Не удалось распознать ссылку. Отправь полную HTTP- или HTTPS-ссылку на YouTube, Instagram или TikTok. | No se reconoció el enlace. Envía un enlace HTTP o HTTPS completo de YouTube, Instagram o TikTok. | handlers |
| Recognized a {platform_label} link, but downloads from this platform aren't enabled yet. | Ссылка {platform_label} распознана, но скачивание с этой платформы пока не подключено. | Se reconoció un enlace de {platform_label}, pero las descargas de esta plataforma aún no están activadas. | handlers |
| YouTube link recognized. Starting download… | Ссылка YouTube распознана. Начинаю скачивание… | Enlace de YouTube reconocido. Iniciando descarga… | handlers |
| Starting download… | Начинаю скачивание… | Iniciando descarga… | handlers, telegram_instagram_posts |
| For /p/ links with img_index, choose all videos or the specified video. | Для /p/ с img_index можно выбрать все видео или указанное видео. | En los enlaces /p/ con img_index, puedes elegir todos los vídeos o el vídeo indicado. | handlers |
| Send a YouTube link or a public Instagram Reel or /p/ link. Only videos are downloaded from carousels, in their original order; with img_index, choose all videos or the specified video. | Отправь ссылку на YouTube, публичный Instagram Reel или /p/. Из каруселей скачиваются только видео, в исходном порядке; для /p/ с img_index можно выбрать все видео или указанное видео. | Envía un enlace de YouTube o de un Reel o publicación /p/ públicos de Instagram. Solo se descargan los vídeos del carrusel, en su orden original; con img_index puedes elegir todos o el vídeo indicado. | handlers |
| This platform isn't supported yet. Send a YouTube, Instagram or TikTok link. | Эта платформа пока не поддерживается. Отправь ссылку на YouTube, Instagram или TikTok. | Esta plataforma aún no es compatible. Envía un enlace de YouTube, Instagram o TikTok. | handlers |
| Something went wrong. Try again later. | Произошла внутренняя ошибка. Попробуй ещё раз позже. | Algo salió mal. Inténtalo más tarde. | handlers |
| This choice has expired. Send the link again. | Выбор устарел. Отправь ссылку заново. | Esta opción ha caducado. Envía el enlace de nuevo. | handlers, telegram_instagram_posts |
| The file is too large to send through Telegram. Try a smaller video. | Файл слишком большой для отправки через Telegram. Попробуй видео меньшего размера. | El archivo es demasiado grande para enviarlo por Telegram. Prueba con un vídeo más pequeño. | handlers |
| Couldn't send the file to Telegram. Try again later. | Не удалось отправить файл в Telegram. Попробуй ещё раз позже. | No se pudo enviar el archivo a Telegram. Inténtalo más tarde. | handlers |
| A Reel is already being processed. Wait for it to finish before sending another link. | Уже обрабатываю Reel. Дождись завершения и отправь ссылку позже. | Ya se está procesando un Reel. Espera a que termine antes de enviar otro enlace. | telegram_instagram |
| Public Reels and /p/ posts are supported. For /p/, use img_index to select an item; other selectors aren't supported. | Поддерживаются публичные Reels и публикации /p/. Для /p/ поддерживается выбор через img_index; другие селекторы не поддерживаются. | Se admiten Reels y publicaciones /p/ públicos. En /p/, usa img_index para elegir un elemento; no se admiten otros selectores. | telegram_instagram |
| Reel link recognized. Starting download… | Ссылка Reel распознана. Начинаю скачивание… | Enlace de Reel reconocido. Iniciando descarga… | telegram_instagram |
| Couldn't confirm video delivery. There will be no automatic retry. | Не удалось подтвердить отправку видео. Автоматического повтора не будет. | No se pudo confirmar la entrega del vídeo. No habrá un reintento automático. | telegram_instagram, telegram_instagram_posts, telegram_tiktok |
| Couldn't download or prepare the Reel within the limits. | Не удалось скачать или подготовить Reel в пределах лимитов. | No se pudo descargar o preparar el Reel dentro de los límites. | telegram_instagram |
| You selected video #{position} in the Instagram carousel. What would you like to download? | Ты выбрал видео №{position} из Instagram-карусели. Что скачать? | Has elegido el vídeo n.º {position} del carrusel de Instagram. ¿Qué quieres descargar? | telegram_instagram_posts |
| Item #{position} is a photo. Photo downloads aren't supported yet. You can download all videos from this post. | Элемент №{position} — фотография. Фото пока не скачиваются. Можно скачать все видео из этой публикации. | El elemento n.º {position} es una foto. Aún no se descargan fotos. Puedes descargar todos los vídeos de esta publicación. | telegram_instagram_posts |
| There is no such item in this post. Check the number in the link. | Такого элемента в публикации нет. Проверь номер в ссылке. | Ese elemento no existe en la publicación. Revisa el número del enlace. | telegram_instagram_posts |
| Couldn't identify the owner of this choice. | Не удалось определить владельца выбора. | No se pudo identificar al propietario de esta opción. | telegram_instagram_posts |
| The bot is busy. Try again later. | Бот занят, попробуй позже. | El bot está ocupado. Inténtalo más tarde. | telegram_instagram_posts, telegram_tiktok |
| Couldn't download or prepare the post within the limits. | Не удалось скачать или подготовить публикацию в пределах лимитов. | No se pudo descargar o preparar la publicación dentro de los límites. | telegram_instagram_posts |
| An Instagram link is already being processed. Send the next one later. | Уже обрабатываю Instagram-ссылку. Отправь следующую позже. | Ya se está procesando un enlace de Instagram. Envía el siguiente más tarde. | telegram_instagram_posts |
| This choice has expired or belongs to another user. | Выбор устарел или принадлежит другому пользователю. | Esta opción ha caducado o pertenece a otro usuario. | telegram_instagram_posts |
| Single Instagram video recognized. Starting download… | Одиночное видео Instagram распознано. Начинаю скачивание… | Vídeo individual de Instagram reconocido. Iniciando descarga… | telegram_instagram_posts |
| Invalid or ambiguous Instagram item number. Use a link with exactly one img_index. | Некорректный или неоднозначный номер элемента Instagram. Нужна ссылка с одним img_index. | El número de elemento de Instagram no es válido o es ambiguo. Usa un enlace con un solo img_index. | telegram_instagram_posts |
| Couldn't confirm delivery of the entire carousel. Some videos may have been delivered; there will be no automatic retry. | Не удалось подтвердить отправку всей карусели. Часть видео могла быть доставлена; автоматического повтора не будет. | No se pudo confirmar la entrega de todo el carrusel. Es posible que se hayan entregado algunos vídeos; no habrá un reintento automático. | telegram_instagram_posts |
| Carousel recognized. Preparing videos to send… | Карусель распознана. Подготавливаю видео к отправке… | Carrusel reconocido. Preparando los vídeos para enviarlos… | telegram_instagram_posts |
| Couldn't prepare or send the carousel. There will be no automatic retry. | Не удалось подготовить или отправить карусель. Автоповтора не будет. | No se pudo preparar o enviar el carrusel. No habrá un reintento automático. | telegram_instagram_posts |
| Instagram is temporarily unavailable. Try again later. | Instagram временно недоступен. Попробуй позже. | Instagram no está disponible temporalmente. Inténtalo más tarde. | telegram_instagram_posts |
| Couldn't download or prepare the video. There will be no automatic retry. | Не удалось скачать или подготовить видео. Автоматического повтора не будет. | No se pudo descargar o preparar el vídeo. No habrá un reintento automático. | telegram_instagram_posts |
| Use a link to the whole post without individual item selectors or unknown parameters. | Нужна ссылка на публикацию целиком без выбора отдельных элементов и неизвестных параметров. | Usa un enlace a la publicación completa, sin selectores de elementos ni parámetros desconocidos. | telegram_instagram_posts |
| Couldn't download or prepare the post within the limits. Incomplete carousels are not sent. | Не удалось скачать или подготовить публикацию в пределах лимитов. Неполные карусели намеренно не отправляются. | No se pudo descargar o preparar la publicación dentro de los límites. No se envían carruseles incompletos. | telegram_instagram_posts |
| All videos in the carousel | Все видео из карусели | Todos los vídeos del carrusel | telegram_instagram_posts |
| Only video #{position} | Только видео №{position} | Solo el vídeo n.º {position} | telegram_instagram_posts |
| No videos are available in this post. Photos aren't downloaded. | В публикации нет доступных видео. Фото не скачиваются. | No hay vídeos disponibles en esta publicación. No se descargan fotos. | telegram_instagram_posts |
| Can't safely download the entire carousel: one or more items are unavailable or unrecognized. | Невозможно безопасно скачать всю карусель: один или несколько элементов недоступны или не распознаны. | No se puede descargar todo el carrusel de forma segura: uno o más elementos no están disponibles o no se reconocen. | telegram_instagram_posts |
| TikTok downloads aren't available for this account right now. | Загрузка TikTok сейчас недоступна для этого аккаунта. | Las descargas de TikTok no están disponibles para esta cuenta en este momento. | telegram_tiktok |
| TikTok downloads are paused after an operation cleanup error. | Загрузка TikTok приостановлена после ошибки завершения операции. | Las descargas de TikTok están en pausa tras un error al finalizar una operación. | telegram_tiktok |
| Send a full or short link to a public TikTok video. | Отправь полную или короткую ссылку на публичное TikTok-видео. | Envía un enlace completo o corto de un vídeo público de TikTok. | telegram_tiktok |
| TikTok link recognized. Starting download… | Ссылка TikTok распознана. Начинаю скачивание… | Enlace de TikTok reconocido. Iniciando descarga… | telegram_tiktok |
| Couldn't safely finish the operation. TikTok downloads are paused. | Не удалось безопасно завершить операцию. Загрузка TikTok приостановлена. | No se pudo finalizar la operación de forma segura. Las descargas de TikTok están en pausa. | telegram_tiktok |
| Couldn't process the TikTok video. | Не удалось обработать TikTok-видео. | No se pudo procesar el vídeo de TikTok. | telegram_tiktok |
| Operation cleanup failed. TikTok downloads are paused. | Ошибка завершения операции. Загрузка TikTok приостановлена. | Falló la finalización de la operación. Las descargas de TikTok están en pausa. | telegram_tiktok |
| Couldn't download or prepare the TikTok video. Try another link. | Не удалось скачать или подготовить TikTok-видео. Попробуй другую ссылку. | No se pudo descargar o preparar el vídeo de TikTok. Prueba con otro enlace. | telegram_tiktok |
| TikTok video | Видео TikTok | Vídeo de TikTok | telegram_tiktok |
| Send a YouTube link, a public Instagram Reel or /p/ link, or a public TikTok video link. | Отправь ссылку на YouTube, публичный Instagram Reel или /p/ либо публичное TikTok-видео. | Envía un enlace de YouTube, de un Reel o publicación /p/ públicos de Instagram, o de un vídeo público de TikTok. | handlers |
| Send a YouTube link or a public TikTok video link. | Отправь ссылку на YouTube или публичное TikTok-видео. | Envía un enlace de YouTube o de un vídeo público de TikTok. | handlers |
| This post has {count} video. The limit is {limit}; no videos will be skipped. / This post has {count} videos. The limit is {limit}; no videos will be skipped. | В публикации {count} видео. Сейчас лимит — {limit}; пропускать остальные не будем. | Esta publicación tiene {count} vídeo. El límite es {limit}; no se omitirá ninguno. / Esta publicación tiene {count} vídeos. El límite es {limit}; no se omitirá ninguno. | Instagram counts; native ngettext; no retry |
| Delivery confirmed: {count} video out of {total}. The rest were not sent; there will be no automatic retry. / Delivery confirmed: {count} videos out of {total}. The rest were not sent; there will be no automatic retry. | Подтверждена отправка {count} из {total} видео. Остальные не отправлены; автоматического повтора не будет. | Entrega confirmada: {count} vídeo de {total}. El resto no se envió; no habrá un reintento automático. / Entrega confirmada: {count} vídeos de {total}. El resto no se envió; no habrá un reintento automático. | Instagram counts; native ngettext; no retry |

## E3 request receipts

The original E1b rows are retained above. The former YouTube starting-download
message is no longer emitted by the E3 direct flow. These two new strings describe
confirmed request state, not progress, successful media delivery or a retry promise.
The same pinned locale is used throughout a valid callback interaction.

| EN source | RU | ES | Context / constraint |
|---|---|---|---|
| YouTube link recognized. If no buttons appear, send the link again. | Ссылка на YouTube распознана. Если кнопки не появятся, отправь ссылку ещё раз. | Enlace de YouTube reconocido. Si no aparecen botones, envía el enlace de nuevo. | Noninteractive receipt before binding; recovery guidance if publication cannot be confirmed. No automatic resend. |
| Download request accepted. Results appear in separate messages. | Запрос на скачивание принят. Результат — отдельным сообщением. | Solicitud de descarga aceptada. El resultado se envía en un mensaje aparte. | Replaces the choice prompt after consume, or the direct-download starting status. Acceptance does not mean upload confirmation, continued activity or a guaranteed terminal notification after cancellation. |

## E4 greeting and terminal results

Nine E4 entries supplement the retained historical rows. /start uses one trusted
platform-list template; disabled platforms are omitted. Legacy greeting strings
remain in catalogs but are not emitted. Terminal success means a positive media
acknowledgement, not verified client playback. Unknown delivery never asserts sent/
not-sent and never promises retry. All valid callbacks keep the request locale.

| EN source | RU | ES | Context / constraint |
|---|---|---|---|
| 👋 Hi! I can help you download videos from {platforms}.<br><br>🔗 Just send a video link.<br><br>If buttons appear, choose the format or quality you want — and I'll send the file right here. | 👋 Привет! Я помогу скачать видео из {platforms}.<br><br>🔗 Просто отправь ссылку на видео.<br><br>Если появятся кнопки, выбери нужный формат или качество — и я пришлю файл прямо сюда. | 👋 ¡Hola! Te ayudo a descargar vídeos de {platforms}.<br><br>🔗 Solo envía un enlace a un vídeo.<br><br>Si aparecen botones, elige el formato o la calidad que quieras y te enviaré el archivo aquí mismo. | E4 presentation only; no media or callback-policy change. |
| YouTube, Instagram and TikTok | YouTube, Instagram и TikTok | YouTube, Instagram y TikTok | E4 presentation only; no media or callback-policy change. |
| YouTube and Instagram | YouTube и Instagram | YouTube e Instagram | E4 presentation only; no media or callback-policy change. |
| YouTube and TikTok | YouTube и TikTok | YouTube y TikTok | E4 presentation only; no media or callback-policy change. |
| ✅ File sent. | ✅ Файл отправлен. | ✅ Archivo enviado. | E4 presentation only; no media or callback-policy change. |
| Telegram delivery wasn't confirmed. The file may have arrived. There will be no automatic retry. | Доставка в Telegram не подтверждена. Возможно, файл уже пришёл. Автоматического повтора не будет. | No se ha confirmado la entrega en Telegram. Puede que el archivo haya llegado. No habrá un reintento automático. | E4 presentation only; no media or callback-policy change. |
| Request interrupted. Delivery isn't confirmed. There will be no automatic retry. | Запрос прерван. Доставка не подтверждена. Автоматического повтора не будет. | Solicitud interrumpida. La entrega no está confirmada. No habrá un reintento automático. | E4 presentation only; no media or callback-policy change. |
| File sent. An error occurred while finishing the request; there will be no automatic retry. | Файл отправлен. При завершении запроса произошла ошибка; автоматического повтора не будет. | Archivo enviado. Se produjo un error al finalizar la solicitud; no habrá un reintento automático. | E4 presentation only; no media or callback-policy change. |
| Instagram selection accepted. Results appear in separate messages. | Выбор для Instagram принят. Результат — отдельным сообщением. | Selección de Instagram aceptada. El resultado se envía en un mensaje aparte. | E4 presentation only; no media or callback-policy change. |
