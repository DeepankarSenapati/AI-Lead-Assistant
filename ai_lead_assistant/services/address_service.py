import frappe


def create_address_for_lead(
    lead_name: str,
    address_data: dict,
) -> str | None:
    """
    Create or update the Personal Address linked to a Lead.
    """

    if not address_data:
        return None

    address_line1 = address_data.get("address_line1")
    city = address_data.get("city")
    country = address_data.get("country")

    if not address_line1 or not city or not country:
        return None

    lead = frappe.get_doc("Lead", lead_name)

    address_title = lead.lead_name or lead_name

    existing_address = frappe.db.sql(
        """
        SELECT parent
        FROM `tabDynamic Link`
        WHERE link_doctype = 'Lead'
          AND link_name = %s
          AND parenttype = 'Address'
        LIMIT 1
        """,
        lead_name,
        as_dict=True,
    )

    address_data_to_save = {
        "address_title": address_title,
        "address_type": "Personal",
        "address_line1": address_line1,
        "address_line2": address_data.get("address_line2"),
        "city": city,
        "state": address_data.get("state"),
        "pincode": address_data.get("pincode"),
        "country": country,
    }

    if existing_address:
        address = frappe.get_doc(
            "Address",
            existing_address[0]["parent"],
        )

        for field, value in address_data_to_save.items():
            if value is not None:
                address.set(field, value)

        address.save()
        return address.name

    address = frappe.get_doc({
        "doctype": "Address",
        **address_data_to_save,
        "links": [
            {
                "link_doctype": "Lead",
                "link_name": lead_name,
            }
        ],
    })

    address.insert()
    return address.name