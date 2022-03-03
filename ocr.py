import base64
import binascii
import csv
import ctypes
import os
import shutil
import subprocess
import sys
import re
import traceback

class OCR:

    ##############################################################################################################
    ##                                               Constants                                                  ##
    ##############################################################################################################

    def __init__(self, debug_mode: bool, aws_request_id: str = None):

        self.debug_mode = debug_mode

        # Status codes and error messages
        self.success_status_code = 200
        self.invalid_base_64_string_status_code = 400
        self.ocr_error_status_code = 500

        # Case: AWS Lambda environment execution.
        if not debug_mode:

            # Output files paths
            # Note: tmp is the only editable directory within Lambda environments.
            self.temp_files_directory_path = os.path.join(os.path.sep, 'tmp')
            self.output_files_prefix       = os.path.join(self.temp_files_directory_path, aws_request_id)
            self.png_output_file_path      = self.output_files_prefix + '.png'
            self.txt_output_file_path      = self.output_files_prefix + '.txt'
            self.tsv_output_file_path      = self.output_files_prefix + '.tsv'

            # Tesseract paths
            # Note: see OCR.give_tesseract_execution_permission for details.
            self.dependency_tesseract_directory_path  = os.path.join(os.getcwd(), 'dependencies', 'tesseract_ocr_linux')
            self.dependency_tesseract_path            = os.path.join(self.dependency_tesseract_directory_path, 'tesseract')
            self.executable_tesseract_path            = os.path.join(self.temp_files_directory_path, 'tesseract')
            self.tesseract_data_prefix_directory_path = os.path.join(self.dependency_tesseract_directory_path, 'tessdata')
            self.tesseract_lib_directory_path         = os.path.join(self.dependency_tesseract_directory_path, 'lib')
            

            # Tesseract CLI command
            self.tesseract_cli_command = 'LD_LIBRARY_PATH={} TESSDATA_PREFIX={} {} {} {} txt tsv'.format(
                self.tesseract_lib_directory_path,
                self.tesseract_data_prefix_directory_path,
                self.executable_tesseract_path,
                self.png_output_file_path,
                self.output_files_prefix
            )

        # Case: local Windows envrionment execution.
        else:

            # Temporary and output paths
            self.temp_files_directory_path = os.getcwd() + os.path.join(os.path.sep, 'temp_files')
            self.output_files_prefix       = os.path.join(self.temp_files_directory_path, 'temp')
            self.png_output_file_path      = self.output_files_prefix + '.png'
            self.txt_output_file_path      = self.output_files_prefix + '.txt'
            self.tsv_output_file_path      = self.output_files_prefix + '.tsv'
            
            # Tesseract path
            self.tesseract_path = os.getcwd() + os.path.join(os.path.sep, 'dependencies', 'tesseract_ocr_windows', 'tesseract')

            # Tesseract CLI command
            # Note: Windows environment execution does not require LD_LIBRARY_PATH and TESSDATA_PREFIX specification.
            self.tesseract_cli_command = '{} {} {} txt tsv'.format(
                self.tesseract_path,
                self.png_output_file_path,
                self.output_files_prefix
            )


    ##############################################################################################################
    ##                                               Functions                                                  ##
    ##############################################################################################################

    # Decodes the Base 64 encoded image and executes Tesseract OCR.
    # Returns a tuple:
    #   1. Status code
    #   2. Recognized text
    #   2. List< Tuple<recognized characters, confidence> >
    def parse_image(self, base_64_string: str) -> (int, str, [(str, int)]):
        # Decode Base 64 string to image.
        try:
            with open(self.png_output_file_path, 'wb') as png_output_file:
                png_output_file.write(base64.b64decode(base_64_string, validate=True))
        except (OSError, binascii.Error):
            return (traceback.format_exc(), self.invalid_base_64_string_status_code)

        # Give Tesseract execution permission if in a production environment and it has not been done.
        if not self.debug_mode and not os.path.isfile(self.executable_tesseract_path):
            self.give_tesseract_execution_permission()

        # Execute OCR on decoded image.
        try:
            subprocess.check_output(self.tesseract_cli_command, shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as exception:
            error_text = traceback.format_exc() + '\n\nCommand output:\n' + str(exception.output)
            return (error_text, self.ocr_error_status_code)

        # Format recognized text.
        text = self.format_output()
        confidence_values = self.get_confidence_values()

        # Delete temporary files.
        os.remove(self.png_output_file_path)
        os.remove(self.txt_output_file_path)
        os.remove(self.tsv_output_file_path)

        # Return recognized text.
        return (self.success_status_code, text, confidence_values)


    # Checks the TSV output for formatting errors & fixes them
    # Returns a string containing the formatted output
    def format_output(self) -> str:

        # Split lines into list and remove trailing \n lines.
        lines = []
        with open(self.txt_output_file_path) as txt_output_file:
            lines = txt_output_file.readlines()
            while lines[-1] == '\n':
                lines.pop()

        # Determine indent for each line.
        with open(self.tsv_output_file_path) as tsv_output_file:
            tsv_data = list(csv.DictReader(tsv_output_file, delimiter='\t'))

            # Remove leading -1 confidence rows except for 1 before the first section.
            for index, row in enumerate(tsv_data):
                if row['conf'] != '-1':
                    tsv_data = tsv_data[index - 1:]     # Leave the -1 confidence row for the first section.
                    break

            # Determine baseline left value.
            baseline_left = sys.maxsize
            for row in tsv_data:
                left_value = int(row['left'])
                if left_value != 0:
                    baseline_left = min(baseline_left, left_value)


            # Determine tab value.
            # IDEA:
            # Determine space left value by checking for two words on the same line.
            # space_value = 2nd_word_left - (1st_word_left + 1st_word_width)
            # tab_value = space_value * 4
            # This is needed because the tab value will be different depending on the zoom level of the picture.
            tab_value = 40
            space_values = []
            for index, row in enumerate(tsv_data):
                if int(row['word_num']) > 1:
                    previous_row = tsv_data[index - 1]
                    space_value = int(row['left']) - (int(previous_row['left']) + int(previous_row['width']))
                    if space_value > 0:
                        space_values.append(space_value)
            if len(space_values) != 0:
                space_values.sort()
                median_space_value = space_values[len(space_values) // 2]
                tab_value = median_space_value * 4


            # Determine indents.
            current_line_value = 0      # Note: line values in the TSV are always order sequentially, but the ordering sometimes restarts back to zero.
            lines_index = -1            # Note: index used to access the local lines list.
            determined_indent = False   # Note: state used to track if the current line's indent has been determined.
            for row in tsv_data:

                # Case: the current row represents has a new line value and the text is non-empty.
                # -> Update current line value and increment lines list index.
                # Notes: this case should be hit by the -1 confidence row preceeding each section of rows that are grouped by the same line value.
                line_value = int(row['line_num'])
                if line_value != current_line_value:
                    current_line_value = line_value
                    determined_indent = False
                    lines_index += 1

                # Case: the line's indent has not been determined and the text is non-empty.
                # -> Calculate indent and append it to the corresponding line.
                elif not determined_indent and row['text'] != '' and not row['text'].isspace():
                    determined_indent = True
                    tab_count = round((int(row['left']) - baseline_left) / tab_value)
                    indent = '\t' * tab_count
                    lines[lines_index] = indent + lines[lines_index]
            
        # Build and return output.
        output = ''.join(lines).strip()                     # Remove leading and trailing whitespace.
        output = re.sub(r'(\s*\n){3,}', '\n\n', output)     # Replace three or more newlines with two.
        return output


    # Reads the TSV output file and constructs a list of recognized strings and their associated confidence value.
    def get_confidence_values(self) -> ctypes.Array:
        conf = []
        with open(self.tsv_output_file_path) as tsvfile:
           reader = csv.reader(tsvfile, delimiter='\t')
           list_iterator = iter(reader)
           next(list_iterator)
           for row in list_iterator:
               if row[11].split():
                   conf.append((row[11], row[10]))
        return conf


    # This method is utilized to create a Tesseract binary with executable permission.
    def give_tesseract_execution_permission(self):

        # Copy Tesseract binary to tmp directory.
        # Note: tmp is the only editable directory within Lambda environments.
        shutil.copyfile(self.dependency_tesseract_path,
                        self.executable_tesseract_path)

        # Change permissions to executable.
        os.chmod(self.executable_tesseract_path, 0o755)
