AI_EXTRACTABLE_FIELDS = {
    "Lead": {
        "salutation",
        "first_name",
        "middle_name",
        "last_name",
        "job_title",
        "company_name",
        "email_id",
        "mobile_no",
        "phone",
        "website",
        "fax",
        "city",
        "state",
        "country",
    },

    "Purchase Receipt": {
        "supplier",
        "posting_date",
        "supplier_delivery_note",
    },
}


AI_EXTRACTABLE_CHILD_FIELDS = {
    "Purchase Receipt": {
        "items": {
            "description",
            "qty",
            "uom",
            "rate",
        }
    }
}