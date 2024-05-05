from lib.client.client import Client
from lib.utilities.file_utilities import get_absolute_file_path
from lib.utilities.file_utilities import file_exists
from lib.file import File

if __name__ == "__main__":
    
    client = Client("127.0.0.1", 8080)

    file_name = 'Archivo.txt'
    directory_of_file_relative_path = '/files/client'

    file_absolute_path = get_absolute_file_path(directory_of_file_relative_path, file_name)
    
    file = File(file_absolute_path, file_name)

    if file_exists(file.absolute_path):

        client.open_conection(file)                              
        client.upload_with_selective_repeat(file)
    else:
        print('No existe el Archivo a subir')