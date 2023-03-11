#!/usr/bin/env python3

import csv
import dataclasses
import datetime
import os
import typing

import dateutil.parser
import pint.errors
import pytimeparse.timeparse
import yaml

unit_registry = pint.UnitRegistry()


# %%

@dataclasses.dataclass
class Choice:
    value: typing.Any
    label: str


@dataclasses.dataclass
class Response:
    id: str
    value: typing.Any


@dataclasses.dataclass
class NormalizationResults:
    fieldnames: list[str]
    filler: dict[str, None]


def date_range(first_date: datetime.datetime,
               last_date: datetime.datetime,
               start_with_first: bool = True
               ) -> typing.Generator[datetime.datetime, None, None]:
    for i in range((last_date - first_date).days):
        yield first_date + datetime.timedelta(days=i + (not start_with_first))

def ask_type(prompt: str,
             type_: type,
             skippable: bool = True):
    response = input(prompt + "\n{}> ".format(type_.__name__))
    if skippable and response == "skip":
        return
    try:
        return type_(response)
    except ValueError:
        ask_type(prompt=prompt, type_=type_, skippable=skippable)


def ask_choice(prompt: str,
               choices: typing.Iterable[Choice],
               skippable: bool = True
               ) -> typing.Optional[Choice]:
    if type(choices) is not list:
        choices = list(choices)
    response = input(prompt +
                     "\n" +
                     "\n".join([str(choice.value) + ") " + choice.label for choice in choices]) +
                     "\nchoice> ")
    if skippable and response == "skip":
        return
    for choice in choices:
        try:
            if type(choice.value)(response) == choice.value:
                return choice
        except ValueError:
            pass
    return ask_choice(prompt=prompt, choices=choices, skippable=skippable)


def ask_yn(prompt: str,
           default: typing.Optional[str] = None,
           skippable: bool = True
           ) -> typing.Optional[str]:
    if default:
        if default not in "yn":
            raise ValueError('Default "{}" not in ["y", "n"]'.format(default))
        response = input(prompt + "\ny/n> ".replace(default, default.upper()))
    else:
        response = input(prompt + "\ny/n> ")
    if skippable and response == "skip":
        return
    elif response == "y":
        return "y"
    elif response == "n":
        return "n"
    elif default and response == "":
        return default
    return ask_yn(prompt=prompt, skippable=skippable)


def ask_date(prompt: str,
             skippable: bool = True
             ) -> typing.Optional[datetime.datetime]:
    response = input(prompt + "\ndateutil.parser.parse> ")
    if skippable and response == "skip":
        return
    try:
        return dateutil.parser.parse(response)
    except dateutil.parser.ParserError:
        return ask_date(prompt=prompt, skippable=skippable)


def ask_duration(prompt: str,
                 skippable: bool = True
                 ) -> typing.Optional[int]:
    response = input(prompt + "\npytimeparse.timeparse.timeparse> ")
    if skippable and response == "skip":
        return
    duration = pytimeparse.timeparse.timeparse(response)
    if duration:
        return duration
    return ask_duration(prompt=prompt, skippable=skippable)


def ask_quantity(prompt: str,
                 unit: str,
                 skippable: bool = True,
                 decimals: float = 2
                 ) -> typing.Optional[typing.Union[int, float]]:
    response = input(prompt + "\npint.util.Quantity.to({})> ".format(unit))
    if skippable and response == "skip":
        return
    try:
        parsed = unit_registry(response)
        if type(parsed) is type(unit_registry(unit)):  # is pint.Quantity doesn't work
            return round(parsed.to(unit).magnitude, decimals)
        return round(parsed, decimals)
    except (pint.errors.UndefinedUnitError, pint.errors.DimensionalityError):
        return ask_quantity(prompt=prompt, unit=unit, skippable=skippable)


# %%

# TODO: can restructure this as a class that wraps around DictWriter and
# automatically applies filler. negates the need for NormalizationResults
def normalize_csv(csv_path: str,
                  fieldnames: typing.Iterable[str],
                  prompt: bool = False
                  ) -> typing.Optional[NormalizationResults]:
    # Can optimize this using OrderedDict or similar, but not expecting there
    # to be a very large number of fieldnames or for this to run very often

    if type(fieldnames) is not list:
        fieldnames = list(fieldnames)

    no_change = NormalizationResults(fieldnames=fieldnames, filler=dict())

    if not os.path.isfile(csv_path):
        return no_change

    with open(csv_path, "r") as f:
        existing_fieldnames = next(csv.reader(f))

    new_only = set(fieldnames) - set(existing_fieldnames)
    old_only = set(existing_fieldnames) - set(fieldnames)
    temp_path = csv_path + ".temp"

    if len(new_only) + len(old_only) == 0:
        return no_change

    print("Need to normalize {}\n- Unique to existing fieldnames: {}\n- Unique to new fieldnames: {}".format(
        csv_path,
        ", ".join(list(old_only)) if len(old_only) > 0 else "",
        ", ".join(list(new_only)) if len(new_only) > 0 else ""
    ))

    if prompt:
        if ask_yn(prompt="Proceed?", default="y", skippable=False) == "n":
            return
        print("")

    # Prefer the order of the existing fieldnames, then append the new fieldnames
    combined_fieldnames = existing_fieldnames + [
        fieldname
        for fieldname in fieldnames
        if fieldname in new_only
    ]
    new_filler = {
        fieldname: None
        for fieldname in new_only
    }
    old_filler = {
        fieldname: None
        for fieldname in old_only
    }

    with open(csv_path, "r") as f_in, open(temp_path, "w") as f_out:
        reader = csv.DictReader(f_in)
        writer = csv.DictWriter(f_out, fieldnames=combined_fieldnames)
        writer.writeheader()
        for old_row in reader:
            writer.writerow({**old_row, **new_filler})

    os.rename(temp_path, csv_path)

    if len(old_only) > 0:
        return NormalizationResults(fieldnames=combined_fieldnames, filler=old_filler)
    return NormalizationResults(fieldnames=combined_fieldnames, filler=dict())


def ask_questions(questions: list[dict[str, typing.Any]],
                  questions_date: typing.Optional[datetime.datetime] = None
                  ) -> list[Response]:
    now = datetime.datetime.now()
    now_ymd = now.strftime("%Y-%m-%d")

    if not questions_date:
        questions_date = now
        print(now.strftime("### Asking questions for %Y-%m-%d (%A).\n"))
        if ask_yn("Do you want to change the date?", default="n", skippable=False) == "y":
            questions_date = ask_date(
                "Please enter a date",
                skippable=False
            )
    else:
        print(questions_date.strftime("### Asking questions for %Y-%m-%d (%A).\n"))

    questions_ymd = questions_date.strftime("%Y-%m-%d")

    responses: list[Response] = [
        Response(id="date", value=questions_ymd),
        Response(id="recorded", value=now_ymd)
    ]

    for i, question in enumerate(questions):

        print("({}/{})".format(i + 1, len(questions)), end=" ")

        # TODO: more dynamic frequency parsing

        if question["frequency"] == "weekdays" and questions_date.weekday() > 4:
            print("Skipping (reason: not a weekday)\n")
            continue

        # TODO: more dynamic question type parsing

        if question["type"] == "choice":
            choice = ask_choice(
                prompt=question["prompt"],
                choices=[Choice(**args) for args in question["choices"]]
            )
            responses.append(Response(
                id=question["id"],
                value=choice.value if type(choice) is Choice else None
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

        elif question["type"] == "duration":
            responses.append(Response(
                id=question["id"],
                value=ask_duration(prompt=question["prompt"])
            ))

        elif question["type"] == "quantity":
            responses.append(Response(
                id=question["id"],
                value=ask_quantity(
                    prompt=question["prompt"],
                    unit=question["unit"],
                    decimals=question["decimals"]
                )
            ))

        print("")

    return responses


def main():
    with open("config.yaml", "r") as f:
        config = yaml.load(f, yaml.Loader)

    normalization_results = normalize_csv(
        csv_path=config["path"],
        fieldnames=["date", "recorded"] + [question["id"] for question in config["questions"]],
        prompt=True
    )
    if not normalization_results:
        return

    # not necessary for now, but can optimize reading the last line if needed:
    # https://stackoverflow.com/a/54278929
    if os.path.isfile(config["path"]):
        with open(config["path"], "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                pass
            last_date = datetime.datetime.strptime(row["date"], "%Y-%m-%d")

    dates_to_ask = list(date_range(
        first_date=last_date,
        last_date=datetime.datetime.now(),
        start_with_first=False
    ))

    if len(dates_to_ask) > 1:
        print("Will ask questions for {} dates: {}".format(
            len(dates_to_ask),
            ", ".join([
                date.strftime("%Y-%m-%d")
                for date in dates_to_ask
            ])
        ))

    print('Type "skip" at any time to skip a question, or ^C to quit.\n')

    for date in dates_to_ask:
        try:
            responses = ask_questions(config["questions"], questions_date=date)
        except KeyboardInterrupt:
            print("\n\nQuitting now\n")
            return

        print("Responses:")
        for response in responses:
            print("- {}: {}".format(response.id, response.value))

        if ask_yn("\nSave these responses?", default="y", skippable=False) == "n":
            print("\nResponses discarded.")
            return

        if not os.path.isfile(config["path"]):
            with open(config["path"], "w") as f:
                csv.DictWriter(f, fieldnames=normalization_results.fieldnames).writeheader()

        with open(config["path"], "a") as f:
            csv.DictWriter(f, fieldnames=normalization_results.fieldnames).writerow({
                **{
                    response.id: response.value
                    for response in responses
                },
                **normalization_results.filler
            })

        print("Wrote out {} responses to {}.\n".format(len(responses), config["path"]))


if __name__ == "__main__":
    main()
