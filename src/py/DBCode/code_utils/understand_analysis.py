# -*- coding: utf-8 -*-
# @Project: DBCode
# @Module: understand_analysis
# @Author: Anonymous
# @Time: 2025/9/11 15:28


import understand


def simple_understand_example():
    """Simple Understand usage example"""
    try:
        # Create or open database
        db = understand.open("/data/user/code/sqlite.und")

        # Analyze code
        # db.analyze()

        # Get all functions
        print("All functions:")
        for func in db.ents("function"):
            print(f"  {func.name()} - {func.type()} - Line number: {func.ref('define').line()}")

        # Get all classes (C++)
        print("\nAll classes:")
        for cls in db.ents("class"):
            print(f"  {cls.name()} - Line number: {cls.ref('define').line()}")

        # Get metrics
        print("\nMetrics:")
        for file in db.ents("file"):
            metrics = file.metric(["CountLineCode", "CountDeclFunction", "Cyclomatic"])
            print(f"  {file.name()}: {metrics}")

    except understand.UnderstandError as e:
        print(f"Error: {e}")


# Run simple example
simple_understand_example()
