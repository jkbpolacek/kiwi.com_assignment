#!/usr/bin/env python3
# might need to remove the '3' depending on your env setup

import datetime  # to check date correctness
import json  # for, well, json
import requests  # for api calls
import argparse  # for processing arguments
import re  # for various regexes
import sys  # for stderr


"""
Obtain and process arguments.
"""


def parseArgs():

    argparser = argparse.ArgumentParser(
        description="Process desired flight information.")

    # One-way or Return will be exclusive to each other, same for cheap/fast
    oneOrReturnGroup = argparser.add_mutually_exclusive_group()
    cheapOrFastGroup = argparser.add_mutually_exclusive_group()

    argparser.add_argument("--date",
                           help="Date in yyyy-mm-dd format",
                           required=True)

    argparser.add_argument("--from",
                           help="Departure location in IATA code",
                           required=True)

    argparser.add_argument("--to",
                           help="Destination in IATA code",
                           required=True)

    argparser.add_argument("--bags",
                           help="Specify number of bags brought",
                           default="0",
                           choices=["0", "1", "2"])

    cheapOrFastGroup.add_argument("--cheapest",
                                  help="Use to find cheapest flight (default)",
                                  action="store_true", default=True)

    cheapOrFastGroup.add_argument("--fastest",
                                  help="Use to find fastest fligh",
                                  action="store_true")

    oneOrReturnGroup.add_argument("--one-way",
                                  help="One-way ticket (default)",
                                  action="store_true", default=True)

    oneOrReturnGroup.add_argument("--return",
                                  help="Specify number of days for return",
                                  type=int)

    args = argparser.parse_args()
    return args


"""
Check if arguments contain proper values.
"""


def checkArgs(argsDict):

    if all([
        re.match(r"[AB-Z]{3}$", argsDict["to"]) is not None,
        re.match(r"[AB-Z]{3}$", argsDict["from"]) is not None,
        re.match(r"\d\d\d\d-\d\d-\d\d$", argsDict["date"]) is not None,
        (argsDict["return"] is None or argsDict["return"] > 0)
    ]):
        try:
            splitDate = list(map(int, argsDict["date"].split("-")))
            datetime.datetime(splitDate[0], splitDate[1], splitDate[2])
        except ValueError:
            print("Impossible date.", file=sys.stderr)
            print(argsDict["date"], file=sys.stderr)
            return 1

    else:
        print("Wrong argument values.", file=sys.stderr)
        print(argsDict, file=sys.stderr)
        return 1

    return 0


"""
Create rest of api call address from parts.
"""


def getRemainingApiAdress(argsDict):

    # First 4 addresses are neccessary for any query
    fromAddress = "flyFrom={}".format(argsDict["from"])
    toAddress = "to={}".format(argsDict["to"])

    date = argsDict["date"].split("-")
    dateFromAddress = "dateFrom={}/{}/{}".format(date[2], date[1], date[0])
    dateToAddress = "dateTo={}/{}/{}".format(date[2], date[1], date[0])

    # type of flight decides whether we use daysInDestintaion
    daysInDestinationToAddress = ""
    daysInDestinationFromAddress = ""

    typeFlightAddress = ""

    if (argsDict["return"] is not None):
        typeFlightAddress = "typeFlight=round"

        daysInDestinationToAddress = "daysInDestinationFrom={}".format(argsDict["return"])

        daysInDestinationFromAddress = "daysInDestinationTo={}".format(argsDict["return"])

    else:
        typeFlightAddress = "typeFlight=one-way"

    # API's helps us to sort by cheapest price or fastest flight
    # Eliminates need to sort manually later (except for one exception)
    sort = ""
    if (not argsDict["fastest"]):
        sort = "sort=price"
    else:
        sort = "sort=duration"

    # Filter to remove empty strings, otherwise we could get "&&&" in address
    result = "&".join(filter(None, [fromAddress, toAddress,
                                    dateFromAddress, dateToAddress,
                                    typeFlightAddress,
                                    daysInDestinationFromAddress,
                                    daysInDestinationToAddress,
                                    sort]))
    return result


"""
Call api and get flight data.
"""


def callAPI(address):

    # Simple request, json processing to get only the required data patr
    apiResponse = requests.get(address)
    return json.loads(apiResponse.text)["data"]


"""
Figure out which flight we want from data.
"""


def pickFlight(argsDict, data):

    chosenFlight = None

    # Handle bags restriction
    if argsDict["bags"] != "0":
        data = list(filter(lambda x: argsDict["bags"] in x["bags_price"],
                           data))

        if checkData(data):
            return None  # If no flights with desired criteria AND bags exist

        # Bags can change price of our flight so we need to readjust
        # if we care for cheap flights
        if not argsDict["fastest"]:
            chosenFlight = min(data,
                               key=lambda x: x["price"]
                               + x["bags_price"][argsDict["bags"]])

    # Because we used API filtering, if we ignore bags / their cost,
    # we can just pick our preferred flight
    if chosenFlight is None:
        chosenFlight = data[0]

    return chosenFlight


"""
Book flight, return response of booking api.
"""


def bookFlight(token, bags):
    URL = "http://128.199.48.38:8080/booking"
    headers = {"Content-type": "application/json"}

    msgBody = json.dumps({"booking_token": token,
                          "bags": bags,
                          "currency": "EUR",
                          "passengers": {
                                            "email": "mock@email.com",
                                            "title": "Mr",
                                            "lastName": "Surname",
                                            "firstName": "Name",
                                            "birthday": "1900-01-01",
                                            "documentID": "A123456B"
                                         }
                          })

    apiResponse = requests.post(URL,
                                headers=headers,
                                data=msgBody)
    return apiResponse


"""
Check if we got any data to use.
"""


def checkData(data):
    if len(data) < 1:
        print("No flight found, probably incorrect args", file=sys.stderr)
        return 1
    return 0


def main():
    try:
        BASEADRESS = "https://api.skypicker.com/flights?"

        argsDict = vars(parseArgs())  # get dictionary of args

        if checkArgs(argsDict):
            return 0

        # Create final address for API call
        APIcallAddress = BASEADRESS + getRemainingApiAdress(argsDict)

        # Call API and get necessary data
        data = callAPI(APIcallAddress)

        if checkData(data):
            return 0

        flight = pickFlight(argsDict, data)
        if flight is None:
            print("No flight found", file=sys.stderr)
            return 0

        # Get unique flight booking token from our preffered flight
        bookingToken = flight["booking_token"]

        # Call booking API, get its response, and final check
        response = json.loads(bookFlight(bookingToken,
                                         int(argsDict["bags"])).text)
        if response['status'] == 'confirmed':
            return response['pnr']

    except Exception as e:
        print("Unknown error: \n", e, file=sys.stderr)
        return 0  # shoudln't happen but you never know


print(main())
