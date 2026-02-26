import re

file_path = "reference/diagnostic_report/Bundle-DiagnosticReport-Lab-example-03.json"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

replacements = {
    "ABC": "[PATIENT_NAME]",
    "1981-01-12": "[PATIENT_DOB]",
    "+919818512600": "[PATIENT_PHONE]",
    "22-7225-4829-5255": "[PATIENT_MRN]",
    "Dr. DEF": "[PRACTITIONER_NAME]",
    "21-1521-3828-3227": "[PRACTITIONER_ID]",
    "Dr. PQR": "[PRACTITIONER_NAME_2]",
    "25-1531-3528-3228": "[PRACTITIONER_ID_2]",
    "XYZ Lab Pvt.Ltd.": "[ORGANIZATION_NAME]",
    "+91 243 2634 1234": "[ORGANIZATION_PHONE]",
    "contact@labs.xyz.org": "[ORGANIZATION_EMAIL]",
    "4567878": "[ORGANIZATION_ID]",
    "645bb0c3-ff7e-4123-bef5-3852a4784813": "[REPORT_ID]",
    "3cf54fc4-0178-4127-bb99-b20711404881": "[HIP_ID]",
    "5234342": "[LAB_REPORT_ID]",
    "2020-07-09T15:32:26.605+05:30": "[DATETIME_1]",
    "2020-07-09 15:32:26+0530": "[DATETIME_1]",
    "2017-05-27T11:46:09+05:30": "[DATETIME_2]",
    "2017-05-27 11:46:09+0530": "[DATETIME_2]",
    "2020-07-09T14:58:58.181+05:30": "[DATETIME_3]",
    "2020-07-09 14:58:58+0530": "[DATETIME_3]",
    "2019-05-29T14:58:58.181+05:30": "[DATETIME_4]",
    "2019-05-29 14:58:58+0530": "[DATETIME_4]",
    "2020-07-10T11:45:33+11:00": "[DATETIME_5]",
    "2020-07-10 11:45:33+1100": "[DATETIME_5]",
    "2020-09-29": "[DATE_1]",
    "2015-07-08T06:40:17Z": "[DATETIME_6]",
    "2015-07-08 06:40:17+0000": "[DATETIME_6]",
    "2020-07-08T06:40:17Z": "[DATETIME_7]",
    "2020-07-08 06:40:17+0000": "[DATETIME_7]",
    "2020-07-08T09:33:27+07:00": "[DATETIME_8]",
    "2020-07-08 09:33:27+0700": "[DATETIME_8]",
    "2020-07-09T07:42:33+10:00": "[DATETIME_9]"
}

for k, v in replacements.items():
    content = content.replace(k, v)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
