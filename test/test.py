def replace_spaces_and_tabs(file_path):
    try:
        with open(file_path, 'r') as file:
            # Читаем содержимое файла
            content = file.read()

            # Ищем индексы первого вхождения "HTML" и первого вхождения "CSS"
            # start_index = content.find('HTML')
            # end_index = content.find('CSS')

            start_index = content.find('CSS')
            end_index = content[start_index + len('HTML'):].find('Styleguide')


            if start_index != -1 and end_index != -1:
                # Извлекаем блок между "HTML" и "CSS"
                block_to_replace = content[start_index + len('HTML'):end_index]

                # Заменяем пробелы и отступы внутри блока на пустое место
                block_without_spaces_and_tabs = block_to_replace.replace('\t', ' ').replace('\n', ' ')

                block_without_spaces_and_tabs = block_without_spaces_and_tabs.replace(' <', '<').replace('< ', '<')
                block_without_spaces_and_tabs = block_without_spaces_and_tabs.replace(' >', '>').replace('> ', '>')

                print(block_without_spaces_and_tabs)

                print(f"Пробелы и отступы в блоке между HTML и CSS в файле {file_path} успешно заменены.")
            else:
                print("Блок между HTML и CSS не найден.")
    except FileNotFoundError:
        print(f"Файл {file_path} не найден.")
    except Exception as e:
        print(f"Произошла ошибка: {e}")


# Пример использования
file_path = 'C:\\Users\\Артем\\Downloads\\content.txt'  # Замените на путь к вашему файлу
replace_spaces_and_tabs(file_path)
