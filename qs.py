#!/usr/bin/env python3

import dataclasses
import datetime
# import functools
import typing

import dateutil.parser
import yaml

# %%

with open("config.yaml", "r") as f:
    config = yaml.load(f, yaml.Loader)


# %%

@dataclasses.dataclass
class Choice:
    value: typing.Any
    label: str


@dataclasses.dataclass
class Response:
    id: str
    value: typing.Any


def ask_type(prompt: str,
             type_: type,
             skippable: bool = True):
    response = input(prompt + "\n> ")
    if skippable and response == "skip":
        return
    try:
        return type_(response)
    except ValueError:
        ask_type(prompt=prompt, type_=type_)


def ask_choice(prompt: str,
               choices: typing.Iterable[Choice],
               skippable: bool = True
               ) -> typing.Optional[Choice]:
    if type(choices) is not list:
        choices = list(choices)
    response = input(prompt +
                     "\n" +
                     "\n".join([str(choice.value) + ") " + choice.label for choice in choices]) +
                     "\n> ")
    if skippable and response == "skip":
        return
    for choice in choices:
        try:
            if type(choice.value)(response) == choice.value:
                return choice
        except ValueError:
            pass
    return ask_choice(prompt=prompt, choices=choices)


def ask_yn(prompt: str,
           default: typing.Optional[str] = None,
           skippable: bool = True
           ) -> typing.Optional[str]:
    if default:
        if default not in "yn":
            raise ValueError('Default "{}" not in ["y", "n"]'.format(default))
        response = input(prompt + " (y/n)\n> ".replace(default, default.upper()))
    else:
        response = input(prompt + " (y/n)\n> ")
    if skippable and response == "skip":
        return
    elif response == "y":
        return "y"
    elif response == "n":
        return "n"
    elif default and response == "":
        return default
    return ask_yn(prompt=prompt)


def ask_date(prompt: str,
             skippable: bool = True
             ) -> typing.Optional[datetime.datetime]:
    response = input(prompt + "\n> ")
    if skippable and response == "skip":
        return
    try:
        return dateutil.parser.parse(response)
    except dateutil.parser.ParserError:
        return ask_date(prompt=prompt)


# ask_functions = {
#     "choice": ask_choice,
#     "yn": ask_yn,
#     "int": functools.partial(ask_type, type_=int),
#     "float": functools.partial(ask_type, type_=float)
# }

# %%

if __name__ == "__main__":
    import csv
    import os

    now = datetime.datetime.now()
    questions_date = datetime.datetime(now.year, now.month, now.day)

    print(now.strftime("Answering questions for %Y-%m-%d."))
    if ask_yn("Do you want to change the date?", default="n", skippable=False) == "y":
        questions_date = ask_date(
            "Please enter a date (will be parsed by dateutil.parser)",
            skippable=False
        )
        questions_date = datetime.datetime(
            questions_date.year,
            questions_date.month,
            questions_date.day
        )

    print('\nType "skip" at any time to skip a question.\n')

    questions_ymd = questions_date.strftime("%Y-%m-%d")

    responses: list[Response] = []

    for i, question in enumerate(config["questions"]):

        print("({}/{})".format(i + 1, len(config["questions"])), end=" ")

        # TODO: more dynamic frequency parsing

        if question["frequency"] == "weekdays" and questions_date.weekday() > 4:
            continue

        # TODO: more dynamic question type parsing

        if question["type"] == "choice":
            responses.append(Response(
                id=question["id"],
                value=ask_choice(
                    prompt=question["prompt"],
                    choices=[Choice(**args) for args in question["choices"]]
                ).value
            ))

        elif question["type"] == "yn":
            responses.append(Response(
                id=question["id"],
                value=ask_yn(prompt=question["prompt"])
            ))

        elif question["type"] == "int":
            responses.append(Response(
                id=question["id"],
                value=ask_type(prompt=question["prompt"], type_=int)
            ))

        elif question["type"] == "float":
            responses.append(Response(
                id=question["id"],
                value=ask_type(prompt=question["prompt"], type_=float)
            ))

        print("\n")

    if not os.path.isfile(config["path"]):
        with open(config["path"], "w") as f:
            f.write('date,id,value\n')

    with open(config["path"], "a") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow([questions_ymd, "date", now.strftime("%Y-%m-%d")])
        for response in responses:
            writer.writerow([questions_ymd, response.id, response.value])

    print("Wrote out {} responses to {}".format(len(responses), config["path"]))