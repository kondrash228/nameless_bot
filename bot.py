import telebot
import openai

openai.api_key = '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'
TOKEN = "5575707129:AAHAdYUkY3DQnfwTTY27K4tj8gbrw18CkOU"

bot = telebot.TeleBot(TOKEN)
filename = 'test2.mp3'

@bot.message_handler(content_types=['voice'])
def voice_processing(message):
    file_info = bot.get_file(message.voice.file_id)
    df = bot.download_file(file_info.file_path)
    with open(filename, 'wb') as new_file:
        new_file.write(df)

    audio_file = open(filename, "rb")
    transcript = openai.Audio.transcribe("whisper-1", audio_file)
    print(transcript['text'])
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system",
             "content": "you fitness trainer, make the program based on the user’s wishes"},
            {"role": "user", "content": str(transcript['text'])}
        ]
    )
    bot.send_message(message.chat.id, completion.choices[0].message.content)


bot.polling()
