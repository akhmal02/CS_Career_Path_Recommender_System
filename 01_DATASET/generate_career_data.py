"""Generate synthetic training rows from the rule-based recommendation engine."""

import random

import pandas as pd
from faker import Faker

from recommendation_rules import CAREER_PROFILES, CATEGORY_CONFIG, QUESTION_OPTIONS


fake = Faker()


def get_rule_based_result(selected_data):
    best_career = None
    highest_score = -1
    for career_key, profile_info in CAREER_PROFILES.items():
        score = 0
        profile = profile_info["profile"]
        for category, config in CATEGORY_CONFIG.items():
            matches = len(set(selected_data[category]) & set(profile[category]))
            score += (config["weight"] * matches) / len(selected_data[category])
        if score > highest_score:
            highest_score = score
            best_career = career_key
    return best_career


def generate_csv(count=1000):
    rows = []
    for index in range(count):
        student = {
            "student_id": 1000 + index,
            "name": fake.name(),
            "email": fake.email(),
            "university_year": random.randint(1, 4),
        }
        selections = {}
        for category, config in CATEGORY_CONFIG.items():
            options = [option[0] for option in QUESTION_OPTIONS[category]]
            picks = random.sample(
                options, random.randint(config["minimum"], config["maximum"])
            )
            selections[category] = picks
            student[category] = "|".join(picks)
        student["target_career"] = get_rule_based_result(selections)
        rows.append(student)

    pd.DataFrame(rows).to_csv("career_training_data.csv", index=False)
    print(f"Created career_training_data.csv with {count} rows.")


if __name__ == "__main__":
    generate_csv(1000)

