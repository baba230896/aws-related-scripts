
#!/usr/bin/env python3

import os
import sys
import argparse
import csv
import subprocess
from datetime import datetime

CSV_DATA = []
BACKUP_DIR_SUFFIX = "backup-sg"

class Logging():
    """Class Logging to print different types of logs"""

    @staticmethod
    def print_log(msg, log_level):
        """Print on stdout"""
        print(datetime.now(), log_level, msg)

    @staticmethod
    def error_and_exit(msg):
        """Print ERROR level logs & exit"""
        Logging.print_log(msg, "ERROR")
        sys.exit(1)

    @staticmethod
    def error(msg):
        """Print ERROR level logs only"""
        Logging.print_log(msg, "ERROR")

    @staticmethod
    def log(msg):
        """Print INFO level logs"""
        Logging.print_log(msg, "INFO")

class ControlClass():
    """Main Class"""

    def __init__(self):
        self.csv_data = None
        self.sg_id_column_index = None
        self.sg_region_column_index = None
        self.sg_name_column_index = None
        self.credentials = {}
        self.backup_path = None

    def read_csv(self, path_to_csv):
        """Read CSV"""
        try:
            with open(path_to_csv, 'r') as csv_fd:
                self.csv_data = csv.reader(csv_fd, delimiter=',')

                for row in self.csv_data:
                    CSV_DATA.append(row)

        except IOError:
            Logging.error_and_exit("Something went wrong while reading {} CSV".format(path_to_csv))

    def run_command(self, cmd):
        """Run command using subprocess"""
        proc = subprocess.Popen(
                        cmd, env=self.credentials, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

        try:
            out, err = proc.communicate()
        except subprocess.TimeoutExpired as exception:
            Logging.error_and_exit("run_process: {} timeout expired for command: ".format(cmd))
            return None, str(exception), -1

        out, err = proc.communicate()
        (ret_out, ret_err, retcode) = (out.decode('utf-8'), err.decode('utf-8'), proc.returncode)

        return (ret_out, ret_err, retcode)


    def create_aws_credentials_env(self, access_key, secret_key):
        """Create environment variables for AWS"""
        self.credentials["PATH"] = os.getenv('PATH')
        self.credentials["AWS_ACCESS_KEY_ID"] = access_key
        self.credentials["AWS_SECRET_ACCESS_KEY"] = secret_key
        self.credentials["AWS_DEFAULT_OUTPUT"] = "json"

    def validate(self, args):
        """Validate Parameters"""
        # Check CSV exists
        if not os.path.isfile(args.input_csv):
            Logging.error_and_exit("{0} CSV not found".format(args.input_csv))

        # Create backup directory
        if args.output_dir:
            self.backup_path = os.path.join(os.path.abspath(args.output_dir), BACKUP_DIR_SUFFIX)
        else:
            self.backup_path = os.path.join(os.getcwd(), BACKUP_DIR_SUFFIX)

        if not os.path.isdir(self.backup_path):
            os.makedirs(self.backup_path)
            Logging.log("{0} Directory created".format(self.backup_path))

        # Read CSV Data for further column name validation
        self.read_csv(args.input_csv)

        try:
            self.sg_id_column_index = CSV_DATA[0].index(args.sg_id)
            self.sg_region_column_index = CSV_DATA[0].index(args.sg_region)
            self.sg_name_column_index = CSV_DATA[0].index(args.sg_name)
        except ValueError:
            Logging.error_and_exit("Column names related with SG are invalid")

        # Verify AWS Credentials
        self.create_aws_credentials_env(args.access_key, args.secret_key)
        _, error, _ = self.run_command(["aws", "sts", "get-caller-identity"])
        if error:
            Logging.error_and_exit("Invalid AWS Credentials")

    def sg_backup(self):
        """Backup Security Group"""
        for security_group in CSV_DATA[1:]:
            Logging.log("Backup Started: SG ID - {0}"
                        .format(security_group[self.sg_id_column_index]))
            desc_sg_command = ["aws", "ec2", "describe-security-groups", "--group-ids",
                                security_group[self.sg_id_column_index]]
            self.credentials["AWS_DEFAULT_REGION"] = security_group[self.sg_region_column_index]
            output, error, _ = self.run_command(desc_sg_command)
            if error:
                Logging.error("{0} Backup Failed. SG doesn't exists.".format(desc_sg_command))
            else:
                try:
                    backup_file_name = security_group[self.sg_name_column_index] + ".json"
                    backup_file = os.path.join(os.path.abspath(self.backup_path), backup_file_name)
                    with open(backup_file, 'w') as backup_fd:
                        backup_fd.write(output)

                    Logging.log("Backup File: {0} for SG ID: {1}"
                                .format(backup_file, security_group[self.sg_id_column_index]))
                except IOError:
                    Logging.error_and_exit("Something went wrong while writing {} CSV"
                                            .format(backup_file))

    def parser_configuration(self):
        """Parse parameters"""
        parser = argparse.ArgumentParser(description="Backup Security Groups")
        parser.add_argument("--access-key", type=str, help="AWS Access Key", required=True)
        parser.add_argument("--secret-key", type=str, help="AWS Secret Key", required=True)
        parser.add_argument("--input-csv", type=str, help="SGs CSV file", required=True)
        parser.add_argument("--sg-id", type=str, help="Column Name of SG ID in CSV", required=True)
        parser.add_argument("--sg-region", type=str,
                            help="Column Name of SG Region in CSV", required=True)
        parser.add_argument("--sg-name", type=str,
                            help="Column Name of SG Name in CSV", required=True)
        parser.add_argument("--output-dir", type=str, help="Output directory for SG Backup files")

        args = parser.parse_args()

        self.validate(args)

    def main(self):
        """Main Function"""
        self.parser_configuration()
        self.sg_backup()

if __name__ == '__main__':
    ControlClass().main()
