import json
import pathlib
import pprint
import re
from time import sleep
from python_console_menu import AbstractMenu, MenuItem
import requests
import youtube_dl
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait


class Scrape(AbstractMenu):

    def __init__(self):
        self.cookie = None
        self.CLASSROOM = "https://www.scaler.com/academy/mentee-dashboard/classes/regular"
        self.MASTERCLASS = "https://www.scaler.com/academy/mentee-dashboard/classes/events/masterclasses"
        self.TYPE = None
        self.DOWNLOAD_PATH = str(pathlib.Path(__file__).parent.absolute()) + r"\output\downloads\\"
        self.driver = None
        self.videoLinks = []
        self.notes = set([])
        super().__init__("Choose an option:")

    def get_cookie(self):
        return self.cookie

    def initialise(self):
        self.add_menu_item(MenuItem(100, "Exit").set_as_exit_option())
        self.add_menu_item(
            MenuItem(101, "Fetch Regular Class", lambda: self.parse_links('regular')))
        self.add_menu_item(
            MenuItem(102, "Fetch Master Class", lambda: self.parse_links('master')))
        self.add_menu_item(MenuItem(103, "Convert Regular Links", lambda: self.fetch_links('regular')))
        self.add_menu_item(MenuItem(104, "Convert Master Links", lambda: self.fetch_links('master')))
        self.add_menu_item(MenuItem(105, "Convert Classroom Notes", lambda: self.download_notes()))

    # Driver init
    def init_driver(self):
        capabilities = DesiredCapabilities.CHROME.copy()
        capabilities['goog:loggingPrefs'] = {"performance": "ALL"}
        chromeOptions = webdriver.ChromeOptions()
        prefs = {"download.default_directory": self.DOWNLOAD_PATH}
        chromeOptions.add_experimental_option("prefs", prefs)
        chromeOptions.add_experimental_option(
            'excludeSwitches', ['enable-logging'])
        print("Initiating Chrome Driver...")
        self.driver = webdriver.Chrome(
            desired_capabilities=capabilities, options=chromeOptions)

    # Network Log Processing
    @staticmethod
    def process_log(_logs):
        # with open("log.json", "w") as log_file:
        #     for entry in _logs:
        #         try:
        #             log = json.loads(entry["message"])["message"]
        #         except KeyError:
        #             continue
        #
        #     pprint.pprint(_logs, stream=log_file)
        for entry in _logs:
            log = json.loads(entry["message"])["message"]
            if "Network.responseReceived" in log["method"]:
                yield log

    # Login
    def login(self, _email, _password):
        self.driver.get(self.CLASSROOM)
        try:
            self.driver.find_element(By.NAME, 'user[email]').send_keys(_email)
            self.driver.find_element(By.NAME, 'user[password]').send_keys(_password)
            self.driver.find_element(By.CSS_SELECTOR, 'button.form__action').click()
        except Exception as e:
            print(f"Unable to login! \n Error: {e}")
            exit(-1)
        network_log = self.process_log(self.driver.get_log("performance"))
        cookie = ''
        for log in network_log:
            try:
                if log['params']['headers']:
                    cookie = log['params']['headers']['set-cookie']
                    break
            except KeyError:
                continue
        self.cookie = cookie.replace('\n', ' ')
        with open("logs/cookie.txt", "w") as cookie_file:
            cookie_file.write(self.get_cookie())

    def convert(self, _name, _url, _type):
        print(f"Converting: {_name}")
        try:
            with open("logs/user_cookie.txt", "r") as cookie_file:
                self.cookie = cookie_file.readline()
            youtube_dl.utils.std_headers['Cookie'] = self.get_cookie()
            youtube_dl.utils.std_headers[
                "User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                                "Chrome/96.0.4664.113 Safari/537.36 "
            youtube_dl.utils.std_headers["Accept-Language"] = "en-US,en;q=0.9"
            ydl_options = {
                "format": "bestaudio/best",
                "outtmpl": f"{self.DOWNLOAD_PATH}{_type}/{_name}.mp4",
                "quiet": True
            }
            with youtube_dl.YoutubeDL(ydl_options) as ydl:
                ydl.download([_url])
        except Exception as e:
            self.logger(e)
            return False
        return True

    # Dumps to text file
    def dump(self, _type):
        with open("logs/notes.txt", "w") as note:
            for n in self.notes:
                note.write(f"{n}\n")
        with open(f"logs/{_type}_links.txt", "w") as file:
            for link in self.videoLinks:
                file.write(f"{link}\n")

    # Logger
    @staticmethod
    def logger(e: Exception):
        with open("log.json", 'a') as log_file:
            pprint.pprint(str(e), stream=log_file)

    # Record m3u8 URLs
    def download(self, _url, _name):
        self.driver.get(_url)
        sleep(2)
        try:
            recordBtn = self.driver.find_element(
                By.CSS_SELECTOR, '.event-card__content-last-button-container')
            try:
                noteButtons = self.driver.find_elements(By.CSS_SELECTOR, '.primary.m-r-10.bold')
                for btn in noteButtons:
                    self.notes.add(f"{_name}||{btn.get_attribute('href')}")
            except NoSuchElementException:
                pass
            recordBtn.click()
            sleep(5)
        except ElementClickInterceptedException:
            sleep(5)
            pass
        except NoSuchElementException:
            sleep(2)
            pass
        events = self.process_log(self.driver.get_log("performance"))
        for event in events:
            try:
                url = event['params']['response']['url']
            except KeyError:
                continue
            if not re.search(".m3u8", url):
                continue
            flag = 0
            for item in self.videoLinks:
                if item == url or url.endswith('stream_0.m3u8') or url.endswith('stream_1.m3u8'):
                    flag = 1
                    break
            if flag:
                continue
            else:
                self.videoLinks.append(f"{_name}||{url}")
                return True
        return False

    @staticmethod
    def download_notes():
        success = 0
        failed = 0
        print("\nDownloading notes.....\n")
        with open("logs/notes.txt") as notes_file:
            lines = list(set(notes_file.readlines()))
            for line in lines:
                content = line.split("||")
                try:
                    response = requests.get(content[1].strip('\n'), allow_redirects=True)
                    if response.status_code == 200:
                        with open(f"output/downloads/regular/notes/{content[0]}.pdf", "wb") as pdf:
                            pdf.write(response.content)
                            print(f"{content[0]}...✅")
                except Exception as e:
                    print(f"Error while converting {content[0]} : {e}")

    def parse_links(self, _type):
        success = 0
        failed = 0
        titles = []
        links = []
        if _type == 'master':
            self.driver.get(self.MASTERCLASS)
            sleep(2)
            elements = self.driver.find_elements(By.CLASS_NAME, 'weekbody-table__topic')
            titles = [elem.text for elem in elements]
            elements = self.driver.find_elements(By.CLASS_NAME, 'day__link')
            links = [elem.get_attribute('href') for elem in elements]
        elif _type == 'regular':
            self.driver.get(self.CLASSROOM)
            sleep(2)
            WebDriverWait(self.driver, 3).until(ec.presence_of_element_located(
                (By.CLASS_NAME, 'icon-plus-circle')))
            icons = self.driver.find_elements(By.CLASS_NAME, 'icon-plus-circle')
            for i in icons:
                i.click()
            elements = self.driver.find_elements(By.CLASS_NAME, 'weekbody-table__col-title-main')
            names = [elem.text for elem in elements]
            titles = list(filter(lambda x: 'contest' not in x.lower(), names))
            titles.reverse()
            elements = self.driver.find_elements(By.CLASS_NAME, 'me-cr-classroom-url')
            hrefs = [elem.get_attribute('href') for elem in elements]
            links = list(filter(lambda x: 'session' in x, hrefs))
            links.reverse()
        print(f"Found {len(links)} items in '{_type}'....")
        count = 0
        for link, name in zip(links, titles):
            name = name.replace(':', '-')
            count = count + 1
            ops = self.download(link, name)
            if ops:
                print(f"[{count}] '{name}'✅!")
                success += 1
            else:
                failed += 1
                with open("logs/failed.txt", 'a') as failed_file:
                    failed_file.write(f"{link}\n")
        print("==================================================")
        print(f"Success: {success}; Failed: {failed}")
        self.dump(_type)
        if _type == "regular":
            self.hide_menu_item(101)
            self.show_menu_item(105)
        else:
            self.hide_menu_item(102)
            self.hide_menu_item(105)

    def fetch_links(self, _type):
        success = 0
        failed = 0
        try:
            with open(f"logs/{_type}_links.txt", "r") as file:
                lines = file.readlines()
                for line in lines:
                    content = line.split("||")
                    if self.convert(content[0], content[1], _type):
                        success = success + 1
                    else:
                        failed = failed + 1
            print("==================================================")
            print(f"Success: {success}; Failed: {failed}")
        except FileNotFoundError:
            print("No Links Found!")
        except Exception as e:
            print("Error!", e)


if __name__ == "__main__":
    print("  \n"
          "      ____            _             ____  _       ____    ___  \n"
          "     / ___|  ___ __ _| | ___ _ __  |  _ \| |     |___ \  / _ \ \n"
          "     \___ \ / __/ _` | |/ _ \ '__| | | | | |       __) || | | |\n"
          "      ___) | (_| (_| | |  __/ |    | |_| | |___   / __/ | |_| |\n"
          "     |____/ \___\__,_|_|\___|_|    |____/|_____| |_____(_)___/ \n"
          "     ")
    email = input("Enter email> ")
    password = input("Enter password> ")
    print("==================================================")
    obj = Scrape()
    obj.init_driver()
    obj.login(email, password)
    obj.display()
