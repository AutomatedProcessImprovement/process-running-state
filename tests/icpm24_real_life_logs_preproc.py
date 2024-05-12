from pathlib import Path
from typing import List

import pandas as pd
from pix_framework.io.event_log import DEFAULT_CSV_IDS, EventLogIDs, DEFAULT_XES_IDS
from pm4py.objects.log.exporter.csv.versions.pandas_csv_exp import get_dataframe_from_log
from pm4py.objects.log.exporter.xes.factory import export_log
from pm4py.objects.log.importer.csv.versions.pandas_df_imp import convert_dataframe_to_event_log
from pm4py.objects.log.importer.xes import factory as xes_import_factory


def read_and_process_datasets(datasets: List[str]):
    for dataset in datasets:
        print(f"\n--- Processing {dataset} ---\n")
        # Define paths
        xes_file_path = f"../inputs/real-life/original/{dataset}.xes.gz"
        output_xes_path = f"../outputs/{dataset}.xes"
        output_csv_path = Path(f"../outputs/{dataset}.csv.gz")
        # Read XES event log
        original_xes_log = xes_import_factory.apply(xes_file_path)
        # Convert to DataFrame and filter if necessary
        csv_log = get_dataframe_from_log(original_xes_log).sort_values(DEFAULT_XES_IDS.case)
        if "lifecycle:transition" in csv_log.columns:
            csv_log = csv_log[csv_log["lifecycle:transition"].isin([
                "complete", "COMPLETE",
                "Closed", "Cancelled",
                "ate_abort", "withdraw"
            ])]
        # Keep only needed columns
        csv_log = csv_log[[DEFAULT_XES_IDS.case, DEFAULT_XES_IDS.activity, DEFAULT_XES_IDS.end_time]]
        print_stats(csv_log, DEFAULT_XES_IDS)
        # Export to XES
        xes_log = convert_dataframe_to_event_log(csv_log)
        export_log(xes_log, output_xes_path, parameters={"compress": True})
        # Export to CSV
        csv_log.rename(columns={
            DEFAULT_XES_IDS.case: DEFAULT_CSV_IDS.case,
            DEFAULT_XES_IDS.activity: DEFAULT_CSV_IDS.activity,
            DEFAULT_XES_IDS.end_time: DEFAULT_CSV_IDS.end_time,
        }, inplace=True)
        csv_log.to_csv(output_csv_path, index=False)


def read_and_process_bpic_2014():
    dataset = "BPIC_2014_Activity_log_for_incidents"
    print(f"\n--- Processing {dataset} ---\n")
    # Define paths
    csv_file_path = f"../inputs/real-life/original/{dataset}.csv"
    output_xes_path = f"../outputs/{dataset}.xes"
    output_csv_path = Path(f"../outputs/{dataset}.csv.gz")
    # Read CSV event log
    log_ids = EventLogIDs(
        case="Incident ID", activity="IncidentActivity_Type",
        resource="Assignment Group", end_time="DateStamp"
    )
    # Read log
    csv_log = pd.read_csv(csv_file_path, sep=";")
    csv_log = csv_log.astype({log_ids.case: object})
    csv_log[log_ids.resource].fillna("NOT_SET", inplace=True)
    csv_log[log_ids.resource] = csv_log[log_ids.resource].apply(str)
    csv_log[log_ids.end_time] = pd.to_datetime(csv_log[log_ids.end_time], utc=True, format="%d-%m-%Y %H:%M:%S")
    csv_log = csv_log.sort_values(log_ids.end_time)
    # Keep only needed columns
    csv_log = csv_log[[log_ids.case, log_ids.activity, log_ids.end_time]]
    print_stats(csv_log, log_ids)
    # Export to XES
    csv_log.rename(columns={
        log_ids.case: DEFAULT_XES_IDS.case,
        log_ids.activity: DEFAULT_XES_IDS.activity,
        log_ids.end_time: DEFAULT_XES_IDS.end_time,
    }, inplace=True)
    xes_log = convert_dataframe_to_event_log(csv_log)
    export_log(xes_log, output_xes_path, parameters={"compress": True})
    # Export to CSV
    csv_log.rename(columns={
        DEFAULT_XES_IDS.case: DEFAULT_CSV_IDS.case,
        DEFAULT_XES_IDS.activity: DEFAULT_CSV_IDS.activity,
        DEFAULT_XES_IDS.end_time: DEFAULT_CSV_IDS.end_time,
    }, inplace=True)
    csv_log.to_csv(output_csv_path, index=False)


def print_stats(event_log: pd.DataFrame, log_ids: EventLogIDs):
    number_cases = len(event_log[log_ids.case].unique())
    number_activities = len(event_log[log_ids.activity].unique())
    number_activity_instances = len(event_log)
    minimum_lenght = min([len(events) for case_id, events in event_log.groupby(log_ids.case)])
    average_lenght = round(number_activity_instances / number_cases)
    maximum_lenght = max([len(events) for case_id, events in event_log.groupby(log_ids.case)])
    print(f"\tCases: {number_cases}\n"
          f"\tActivities: {number_activities}\n"
          f"\tActivity Instances: {number_activity_instances}\n"
          f"\tMin length: {minimum_lenght}\n"
          f"\tAvg length: {average_lenght}\n"
          f"\tMax length: {maximum_lenght}\n\n")


if __name__ == '__main__':
    read_and_process_datasets([
        "BPIC_2011_hospital_log",
        "BPIC_2012",
        "BPIC_2013_closed_problems",  # These logs get reduced to only 1 event per case, also the activity
        "BPIC_2013_incidents",  # names go from ["Queued", "Accepted", "Completed", "Unmatched"] to just
        "BPIC_2013_open_problems",  # ["Completed"], etc. bit shitty process
        "BPIC_2015_1",
        "BPIC_2015_2",
        "BPIC_2015_3",
        "BPIC_2015_4",
        "BPIC_2015_5",
        "BPIC_2017",
        "BPIC_2018",
        "BPIC_2019",
        "BPIC_2020_DomesticDeclarations",
        "BPIC_2020_InternationalDeclarations",
        "BPIC_2020_PrepaidTravelCost",
        "BPIC_2020_RequestForPayment",
        "BPIC_2020_TravelPermitData",
        "Road_Traffic_Fine_Management_Process",
        "Sepsis_Cases",
    ])
    read_and_process_bpic_2014()
