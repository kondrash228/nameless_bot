import openai

context = []

openai.api_key = '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'
"""
КОМАНДЫ

q - выйти 
cls - очистить контекст
change_role - сменить роль БЕЗ ОЧИСТКИ ПРЕДЫДУЩЕГО КОНТЕКСТА
change_role_clean - сменить роль C ОЧИСТКОЙ ПРЕДЫДУЩЕГО КОНТЕКСТА
"""

model_name = "gpt-4"


context.append({"role": "system",
                        "content": "Твоя задача сделать анкету по данным предоставлеными пользователем. Формат анкеты следующий:имя,пол,возраст,уровень физической подготовки (от 1 до 10),длительность занятия,физические ограничения,наличие спортивного инвентаря,пожелания по упражнениям. Не задавай вопрос про пол (гендер) пользователя,определи пол по имени. Общайся с пользователем на «ты». Задавай уточняющие вопросы до тех пор пока анкету не заполнишь полностью. Задавай вопросы строго по анкете. Задавай по одному вопросу за раз."})

def main():
    while True:

        user_input = (input("ваш вопрос: "))
        context.append({"role": "user", "content": user_input})

        completion = openai.ChatCompletion.create(
            model=model_name,
            messages=context
        )

        print(completion.choices[0].message.content)


main()
