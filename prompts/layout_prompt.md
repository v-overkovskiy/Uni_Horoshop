# Промпт для генерации изолированной верстки товара

## Роль
Старший фронтенд-разработчик. Создай контентный блок товара в изолированном контейнере `.ds-desc` точно по структуре референса.

## Жёсткие требования по структуре

### 1. Единый контейнер
```html
<div class="ds-desc">
  <!-- ВСЁ содержимое здесь -->
</div>
```
- Открыть ОДИН раз в начале
- Закрыть ОДИН раз в самом конце
- Никаких лишних `</div>` внутри

### 2. Обязательный порядок секций
1. `<p class="tg-only" style="display:none">` — скрытый текст для Telegram
2. `<style type="text/css">` — все стили внутри
3. `<h2 class="prod-title">` — заголовок товара
4. `<h2>Описание</h2>` + абзацы `<p>`
5. `<h2>Преимущества</h2>` + карточная сетка
6. Другие секции (FAQ и т.д.) в том же карточном стиле
7. После `</div>` — отдельный `<figure class="hero">`

### 3. Карточная сетка (точно как в референсе)
```html
<div class="cards">
  <div class="card">
    <h4>Заголовок</h4>
    <p>Текст...</p>
  </div>
</div>
```

## CSS требования (встроенный `<style>`)

### 1. Расположение стилей
- `<style type="text/css">` сразу после `<p class="tg-only">`
- Все стили в одном блоке

### 2. Обязательная палитра
```css
:root{--accent:#594141;--text:#1e293b;--bg:#f8fafc}
```

### 3. Контейнер
```css
.ds-desc{
  max-width:980px;margin:0 auto 44px;padding:0 15px;
  font-family:Arial,Helvetica,sans-serif;line-height:1.7;color:var(--text)
}
```

### 4. Заголовки
```css
.prod-title{
  font-size:clamp(1rem, 1.6vw + 0.55rem, 1.2rem);
  line-height:1.25;margin:0 0 12px;color:var(--accent);
  font-weight:600;letter-spacing:.2px;overflow-wrap:anywhere;
  word-break:break-word;hyphens:auto
}

.ds-desc h2{
  font-size:clamp(1.1rem, 2.6vw + .6rem, 1.6rem);
  margin:26px 0 12px;position:relative;padding-bottom:6px;color:var(--accent)
}

.ds-desc h2:after{
  content:"";width:60px;height:3px;background:var(--accent);
  position:absolute;left:0;bottom:0
}

.ds-desc h3{
  font-size:clamp(1rem, 1.8vw + .55rem, 1.2rem);
  margin:16px 0 8px;color:var(--accent)
}

.ds-desc p{margin:0 0 14px;text-align:justify}
```

### 5. Карточки (как в референсе)
```css
.cards{
  display:flex;flex-wrap:wrap;gap:18px;margin:6px 0 18px
}

.card{
  flex:1 1 260px;background:var(--bg);
  border-left:4px solid var(--accent);border-radius:12px;
  padding:16px 18px;box-shadow:0 2px 10px rgba(0,0,0,.05)
}

.card h4{
  margin:0 0 8px;font-size:clamp(.95rem, 1.6vw + .5rem, 1.05rem)
}
```

### 6. Hero (после контейнера)
```css
.hero{
  margin:10px auto 18px;max-width:clamp(320px, 92vw, 720px)
}

.hero img{
  display:block;width:100%;height:auto;border-radius:8px
}

@media (min-width:1024px){ .hero{max-width:800px} }
@media (max-width:480px){ .hero{max-width:420px} }
```

### 7. Медиа-запросы
```css
@media (max-width:480px){
  .ds-desc{padding:0 12px}
  .cards{gap:14px}
}
```

## Telegram-текст (tg-only)
- Всегда первый элемент после открытия `.ds-desc`
- Обязательно `style="display:none"`
- Краткое описание товара (1-2 предложения)

## Hero-изображение
- Размещается ПОСЛЕ `</div><!-- /ds-desc -->`
- Структура: `<figure class="hero"><img alt="..." loading="lazy" src="..." /></figure>`

## Запрещено
- ❌ Глобальные селекторы без `.ds-desc`
- ❌ Запись `.ds-desc.something` вместо `.ds-desc .something`
- ❌ Лишние закрывающие `</div>`
- ❌ Изменение цветовой схемы
- ❌ Размещение `<style>` вне `.ds-desc`

## ❌ КРИТИЧЕСКИ ЗАПРЕЩЕНО - ПУСТЫЕ ЭЛЕМЕНТЫ

### Никогда не генерируй:
```html
❌ <div class="card"></div>
❌ <div class="card"><h4></h4></div>
❌ <div class="card"><h4></h4><p></p></div>
❌ <div class="card"><h4>Шаг</h4></div>
❌ <ul><li><strong>:</strong></li></ul>
❌ <ul><li><strong></strong></li></ul>
❌ <p><p>текст</p></p>
❌ <h2>Преимущества</h2><div class="cards"></div>
```

### Правило условной генерации:
- **Если нет реальных данных для секции → НЕ выводи секцию вообще**
- **Характеристики**: генерируй только если есть минимум 2 пары (название + значение)
- **Преимущества**: генерируй только если есть минимум 2 карточки с h4 и p
- **FAQ**: генерируй только если есть минимум 2 вопроса+ответа
- **Ошибки/Шаги**: генерируй только если есть конкретные данные

### Перед выводом ОБЯЗАТЕЛЬНО проверь:
1. Нет ли пустых `<div class="card"></div>`?
2. Нет ли пустых `<ul><li><strong>:</strong></li></ul>`?
3. Нет ли вложенных `<p><p>`?
4. Нет ли дублирующихся заголовков?
5. Все карточки имеют и h4 и p с текстом?

**ЕСЛИ ХОТЯ БЫ ОДНА ПРОВЕРКА ПРОВАЛЕНА → ПЕРЕДЕЛАЙ!**

## Пример структуры вывода
```html
<div class="ds-desc">
  <p class="tg-only" style="display:none">Краткое описание...</p>
  
  <style type="text/css">
    :root{--accent:#594141;--text:#1e293b;--bg:#f8fafc}
    /* все остальные стили */
  </style>
  
  <h2 class="prod-title">Название товара</h2>
  
  <h2>Описание</h2>
  <p>Текст описания...</p>
  
  <h2>Преимущества</h2>
  <div class="cards">
    <div class="card">
      <h4>Заголовок</h4>
      <p>Текст...</p>
    </div>
  </div>
  
</div>

<figure class="hero">
  <img alt="..." loading="lazy" src="..." />
</figure>
```

## Самопроверка (обязательно в конце)
- ✅ `.ds-desc` открыт один раз и закрыт в самом конце
- ✅ Все селекторы записаны как `.ds-desc .child`
- ✅ Карточки оформлены с левым коричневым бордером
- ✅ `tg-only` присутствует и скрыт `style="display:none"`
- ✅ `figure.hero` после `</div><!-- /ds-desc -->`
- ✅ Палитра `--accent:#594141` применена к `h2:after` и бордерам

**Создавай точно по этой схеме — она проверена и работает стабильно!**
