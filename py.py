import re

from lxml import etree
import xml.etree.ElementTree as ET
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

SITE_URL = "https://www.farfetch.com/ca/shopping/women/dresses-1/items.aspx"
COLUMNS = [
    "id",
    "item_group_id",
    "mpn",
    # "gtin", # not exist
    "title",
    "description",
    "image_link",
    # "additional_image_link",
    "link",
    "gender",
    "age_group",
    "brand",
    # "color",
    # "size",
    "availability",
    "price",
    # "condition",
    "product_type",
    "google_product_category",
]

GENDER_MAP = {"Women": "female"}

ITEM_GROUP_ID = 1

PARSE = False

DATAFRAME_NAME = "farfetch_item_120_2024_05_12.csv"


def initialize_driver() -> WebDriver:
    """
    initialize driver with arguments
    :return WebDriver: driver instance
    """
    # driver setting
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless') # ensure GUI is off
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    return driver


def get_availability(driver: WebDriver) -> str:
    """
    function to check availability
    :param WebDriver driver: driver instance
    :return str: availability
    """

    # check if dress out of stock
    button_text = driver.find_element(
        By.CSS_SELECTOR, "button[data-component='AddToBag']"
    ).text
    try:
        out_of_stock = driver.find_element(
            By.CSS_SELECTOR, "h2[data-component='PageTitleHeading']"
        ).text
    except Exception as e:
        out_of_stock = str(e)

    if button_text == "Pre-order":
        return "preorder"
    elif out_of_stock == "Sorry, this piece is currently out of stock":
        return "out_of_stock"
    else:
        return "in_stock"


def item_page(
    driver: WebDriver,
    wait: WebDriverWait,
    farfetch_item: pd.DataFrame,
) -> pd.DataFrame:
    """
    parsing out data such as: link, product_type, gender, id, item_group_id, mpn,
     availability, google_product_category
    :param WebDriver driver: web driver
    :param WebDriverWait wait: web driver wait
    :param pd.DataFrame farfetch_item: dress item
    :return pd.DataFrame: dress with additional parameters
    """

    # get Breadcrumbs string
    product_type_full_string = wait.until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "nav[data-component='BreadcrumbsNavigation']")
        )
    ).text
    farfetch_item["product_type"] = product_type_full_string.replace("\n", " &gt; ")

    # parse dress link
    farfetch_item["link"] = driver.current_url

    # parse gender
    farfetch_item["gender"] = GENDER_MAP[product_type_full_string.split(" ")[0]]

    info_section = wait.until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, 'div[data-component="InnerPanel"]')
        )
    )

    # get item id
    pattern = r"FARFETCH\s+ID:\s+(\d+)"
    farfetch_item["id"] = re.search(pattern, info_section.text).group(1)

    farfetch_item["item_group_id"] = ITEM_GROUP_ID
    farfetch_item["mpn"] = ITEM_GROUP_ID

    farfetch_item["availability"] = get_availability(driver)

    # google id for dresses
    farfetch_item["google_product_category"] = "2271"

    return farfetch_item


def parse_farfetch(farfetch_df: pd.DataFrame) -> pd.DataFrame:
    """
    parse from site farfetch
    :param pd.DataFrame farfetch_df: empty dataframe
    :return pd.DataFrame: dataframe with parsed data
    """
    driver = initialize_driver()
    driver.get(SITE_URL)

    num_page = 0

    while num_page != 243 or len(farfetch_df) != 120:
        wait = WebDriverWait(driver, 80)

        try:
            # wait until the element is visible
            wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "ul[data-testid='product-card-list']")
                )
            )

            # get all dresses
            dress_collection = driver.find_elements(
                By.CSS_SELECTOR, "li[data-testid='productCard']"
            )

            for index, dress in enumerate(dress_collection):

                # wait until the element is visible
                wait.until(
                    EC.element_to_be_clickable(
                        (
                            By.CSS_SELECTOR,
                            f"li[data-testid='productCard']:nth-child({index + 1})",
                        )
                    )
                )

                # create empty item info
                farfetch_item = pd.DataFrame(columns=COLUMNS, index=[0])

                # parse brand
                brand = dress.find_element(
                    By.CSS_SELECTOR, "p[data-component='ProductCardBrandName']"
                ).text
                farfetch_item["brand"] = brand

                # scroll to make dress visible
                driver.execute_script("arguments[0].scrollIntoView()", dress)

                # parse description
                description = dress.find_element(
                    By.CSS_SELECTOR, "p[data-component='ProductCardDescription']"
                ).text
                farfetch_item["description"] = description

                # generate title
                farfetch_item["title"] = f"{brand} - {description}"

                # parse and process price
                price = dress.find_element(
                    By.CSS_SELECTOR, "p[data-component='Price']"
                ).text
                farfetch_item["price"] = price[1:].replace(",", "") + ".00 USD"

                # parse image
                image = dress.find_element(
                    By.CSS_SELECTOR, "img[data-component='ProductCardImagePrimary']"
                )
                farfetch_item["image_link"] = image.get_attribute("src")

                farfetch_item["age_group"] = "adult"

                href = dress.find_element(
                    By.CSS_SELECTOR, "a[data-component='ProductCardLink']"
                ).get_attribute("href")

                # open dress in a new tab
                driver.execute_script(f"""window.open("{href}","_blank");""")
                driver.switch_to.window(driver.window_handles[1])

                # Going to the page of the item
                # and parsing out data such as: link, product_type, gender, id, item_group_id, mpn, availability, google_product_category
                farfetch_item = item_page(driver, wait, farfetch_item)

                # return to main page
                driver.close()
                driver.switch_to.window(driver.window_handles[0])

                farfetch_df = pd.concat([farfetch_df, farfetch_item], ignore_index=True)
                if len(farfetch_df) == 120:
                    break
                print(f"{index} has been passed")
        except Exception as e:
            print(e)
            driver.quit()

        if len(farfetch_df) == 120:
            farfetch_df.to_csv(DATAFRAME_NAME)
            break

        # move to next page
        button_next = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[data-testid="page-next"]'))
        )
        button_next.click()
    return farfetch_df


def convert_to_feed(farfetch_df: pd.DataFrame, root_name: str, row_name: str) -> bytes:
    """
    convert to xml
    :param pd.DataFrame farfetch_df: dataframe with items
    :param str root_name: root name in xml
    :param str row_name: row name in xml
    :return bytes: xml string in bytes
    """
    root = ET.Element(root_name)
    ET.SubElement(root, "description").text = "FarFetch"

    for _, row in farfetch_df.iterrows():
        item = ET.SubElement(root, row_name)
        for key, value in row.items():
            ET.SubElement(item, key).text = str(value)

    xml_string = ET.tostring(root, method="xml")
    tree = etree.XML(xml_string)

    return etree.tostring(tree, pretty_print=True)


def main():
    # parse from site
    if PARSE:
        farfetch_df = pd.DataFrame(columns=COLUMNS)
        farfetch_df = parse_farfetch(farfetch_df)
    # read from dataframe
    else:
        farfetch_df = pd.read_csv(DATAFRAME_NAME)
        farfetch_df.drop(columns=farfetch_df.columns[0], axis=1, inplace=True)

    xml_string = convert_to_feed(farfetch_df, "channel", "item")

    with open("farfetch_dresses_feed.xml", "wb") as f:
        f.write(xml_string)


if "__main__" == __name__:
    main()
