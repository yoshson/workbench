import datetime as dt
from decimal import Decimal

from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone
from django.utils.translation import deactivate_all

from freezegun import freeze_time

from workbench import factories
from workbench.deals.models import Deal
from workbench.deals.reporting import accepted_deals
from workbench.templatetags.workbench import deal_group
from workbench.tools.formats import local_date_format


class DealsTest(TestCase):
    def setUp(self):
        deactivate_all()

    def test_list(self):
        deal = factories.DealFactory.create()
        self.client.force_login(deal.owned_by)

        self.assertEqual(self.client.get("/deals/").status_code, 200)
        self.assertEqual(self.client.get("/deals/?s=").status_code, 200)
        self.assertEqual(self.client.get("/deals/?s=all").status_code, 200)
        self.assertEqual(self.client.get("/deals/?s=10").status_code, 200)
        self.assertEqual(self.client.get("/deals/?s=20").status_code, 200)
        self.assertEqual(self.client.get("/deals/?s=30").status_code, 200)
        self.assertEqual(self.client.get("/deals/?s=40").status_code, 302)

    def test_detail(self):
        deal = factories.DealFactory.create()
        deal.values.create(type=factories.ValueTypeFactory.create(), value=42)
        deal.save()

        self.client.force_login(deal.owned_by)
        response = self.client.get(deal.urls["detail"])
        # print(response, response.content.decode("utf-8"))
        self.assertContains(response, "42.00")

    def test_crud(self):
        person = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create()
        )
        self.client.force_login(person.primary_contact)

        response = self.client.post(
            "/deals/create/",
            {
                "customer": person.organization.id,
                "contact": person.id,
                "title": "Some deal",
                "probability": Deal.NORMAL,
                "owned_by": person.primary_contact_id,
            },
        )
        self.assertEqual(response.status_code, 302)
        deal = Deal.objects.get()
        self.assertIsNone(deal.closed_on)
        self.assertEqual(
            deal.pretty_status,
            "Open since {}".format(local_date_format(dt.date.today())),
        )

        response = self.client.post(
            deal.urls["set_status"] + "?status={}".format(Deal.DECLINED),
            {
                "closing_type": factories.ClosingTypeFactory.create(
                    represents_a_win=False
                ).pk,
            },
        )
        self.assertRedirects(response, deal.urls["detail"])

        response = self.client.get(deal.urls["update"])
        self.assertContains(response, "This deal is already closed.")

        deal.refresh_from_db()
        self.assertEqual(deal.closed_on, dt.date.today())
        self.assertEqual(
            deal.pretty_status,
            "declined on {}".format(local_date_format(dt.date.today())),
        )

        response = self.client.post(
            deal.urls["set_status"] + "?status={}".format(Deal.OPEN),
        )
        self.assertRedirects(response, deal.urls["detail"])

        deal.refresh_from_db()
        self.assertIsNone(deal.closed_on)
        self.assertEqual(
            deal.pretty_status,
            "Open since {}".format(local_date_format(dt.date.today())),
        )

    def test_protected_m2m(self):
        deal = factories.DealFactory.create()
        group = factories.AttributeGroupFactory.create()
        value = group.attributes.create(title="Test", position=0)
        deal.attributes.add(value)

        with self.assertRaises(ProtectedError):
            group.delete()

    def test_values_and_attributes(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)

        type1 = factories.ValueTypeFactory.create()
        type2 = factories.ValueTypeFactory.create(title="programming")

        group1 = factories.AttributeGroupFactory.create(title="G1")
        self.assertEqual(str(group1), "G1")
        attribute1_1 = group1.attributes.create(title="A1.1")
        group1.attributes.create(title="A1.2")
        group1.attributes.create(title="A1.3", is_archived=True)

        group2 = factories.AttributeGroupFactory.create(is_required=False)
        group2.attributes.create(title="A2.1")
        group2.attributes.create(title="A2.2")

        group3 = factories.AttributeGroupFactory.create(is_archived=True)
        group3.attributes.create(title="A3.1")

        response = self.client.get(Deal.urls["create"])
        self.assertContains(response, type1.title)
        self.assertContains(response, "A1.1")
        self.assertNotContains(response, "A1.3")
        self.assertContains(response, "A2.1")
        self.assertNotContains(response, "A3.1")

        person = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create()
        )
        self.client.force_login(person.primary_contact)

        response = self.client.post(
            "/deals/create/",
            {
                "customer": person.organization.id,
                "contact": person.id,
                "title": "Some deal",
                "probability": Deal.NORMAL,
                "owned_by": person.primary_contact_id,
                "value_{}".format(type1.id): 200,
                "value_{}".format(type2.id): "",
                "attribute_{}".format(group1.pk): attribute1_1.pk,
                "attribute_{}".format(group2.pk): "",
            },
        )
        self.assertEqual(response.status_code, 302)

        deal = Deal.objects.get()
        self.assertEqual(deal.value, 200)
        self.assertEqual(deal.values.count(), 1)

        da = deal.dealattribute_set.get()
        self.assertEqual(da.attribute, attribute1_1)
        self.assertEqual(
            str(da),
            "Some deal {} - A1.1".format(person.primary_contact.get_short_name()),
        )

        response = self.client.get(deal.urls["update"])
        self.assertContains(
            response,
            '<input class="form-check-input" type="radio" name="attribute_%(g)s" value="%(a)s" class="my-2" required id="id_attribute_%(g)s_0" checked>'  # noqa
            % {"g": attribute1_1.group_id, "a": attribute1_1.id},
            html=True,
        )

    def test_set_status(self):
        deal = factories.DealFactory.create()
        self.client.force_login(deal.owned_by)

        response = self.client.get(deal.urls["set_status"] + "?status=10")
        self.assertNotContains(response, "closing_type")
        self.assertNotContains(response, "closing_notice")

        response = self.client.get(deal.urls["set_status"] + "?status=20")
        self.assertContains(response, "Award of contract")

        response = self.client.get(deal.urls["set_status"] + "?status=30")
        self.assertContains(response, "Reason for losing")

        response = self.client.get(deal.urls["set_status"] + "?status=40")
        self.assertEqual(response.status_code, 404)

        response = self.client.post(deal.urls["set_status"] + "?status=20")
        self.assertContains(response, "This field is required when closing a deal.")

    @freeze_time("2020-02-18")
    def test_badge(self):
        self.assertEqual(
            factories.DealFactory.create().status_badge,
            '<span class="badge badge-info">Open since 18.02.2020</span>',
        )
        self.assertEqual(
            factories.DealFactory.create(
                status=Deal.ACCEPTED, closed_on=dt.date.today()
            ).pretty_status,
            "accepted on 18.02.2020",
        )

    def test_xlsx(self):
        deal = factories.DealFactory.create()

        group = factories.AttributeGroupFactory.create()
        attribute = group.attributes.create(title="Test", position=0)
        deal.attributes.add(attribute)

        deal.values.create(type=factories.ValueTypeFactory.create(), value=42)
        deal.save()

        self.client.force_login(deal.owned_by)
        response = self.client.get("/deals/?xlsx=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["content-type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_decision_expected_on_conditionally_required(self):
        person = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create()
        )
        self.client.force_login(person.primary_contact)

        response = self.client.post(
            "/deals/create/",
            {
                "customer": person.organization.id,
                "contact": person.id,
                "title": "Some deal",
                "probability": Deal.HIGH,
                "owned_by": person.primary_contact_id,
            },
        )
        self.assertContains(response, "This field is required when probability is high")

    def test_decision_expected_on_status(self):
        today = dt.date.today()
        deal = Deal(decision_expected_on=today)
        self.assertEqual(
            deal.pretty_status,
            "Decision expected on {}".format(local_date_format(today)),
        )
        self.assertIn("badge-info", deal.status_badge)

        deal = Deal(decision_expected_on=today - dt.timedelta(days=1))

        self.assertEqual(
            deal.pretty_status,
            "Decision expected on {}".format(
                local_date_format(today - dt.timedelta(days=1))
            ),
        )
        self.assertIn("badge-warning", deal.status_badge)

    def test_caveat_status(self):
        self.assertIn(
            "badge-info",
            Deal(created_at=timezone.now() - dt.timedelta(days=30)).status_badge,
        )
        self.assertIn(
            "badge-caveat",
            Deal(created_at=timezone.now() - dt.timedelta(days=360)).status_badge,
        )

    def test_update_with_archived_valuetype(self):
        vt = factories.ValueTypeFactory.create(is_archived=True)
        deal = factories.DealFactory.create()
        deal.values.create(type=vt, value=200)
        deal.save()

        deal.refresh_from_db()
        self.assertEqual(deal.value, 200)

        self.client.force_login(deal.owned_by)
        response = self.client.get(deal.urls["update"])

        self.assertContains(response, 'name="value_{}"'.format(vt.id))
        self.assertContains(response, 'value="200.00"')

        self.assertNotContains(
            self.client.get(deal.urls["create"]), 'name="value_{}"'.format(vt.id)
        )

        response = self.client.post(
            deal.urls["update"],
            {
                "customer": deal.customer_id,
                "contact": deal.contact_id,
                "title": deal.title,
                "probability": Deal.NORMAL,
                "owned_by": deal.owned_by_id,
                "value_{}".format(vt.id): 500,
            },
        )
        self.assertRedirects(response, deal.urls["detail"])
        deal.refresh_from_db()
        self.assertEqual(deal.value, 500)

    def test_deal_group(self):
        def offset(offset=0):
            return dt.date.today() + dt.timedelta(days=offset)

        self.assertEqual(deal_group(Deal())[0], 5)
        self.assertEqual(deal_group(Deal(probability=Deal.NORMAL))[0], 4)
        self.assertEqual(deal_group(Deal(probability=Deal.HIGH))[0], 3)
        self.assertEqual(
            deal_group(Deal(probability=Deal.HIGH, decision_expected_on=offset(90)))[0],
            3,
        )
        self.assertEqual(
            deal_group(Deal(probability=Deal.HIGH, decision_expected_on=offset(30)))[0],
            2,
        )
        self.assertEqual(
            deal_group(Deal(probability=Deal.HIGH, decision_expected_on=offset(20)))[0],
            1,
        )

    def test_deal_reporting(self):
        deal = factories.DealFactory.create(
            status=Deal.ACCEPTED, closed_on=dt.date.today()
        )
        vt1 = factories.ValueTypeFactory.create(position=1)
        vt2 = factories.ValueTypeFactory.create(position=0)
        deal.values.create(type=vt1, value=200)
        deal.values.create(type=vt2, value=400)
        deal.save()

        self.client.force_login(deal.owned_by)

        response = self.client.get(
            "/report/accepted-deals/?date_from=2020-01-01&date_until=2099-01-01"
        )
        self.assertContains(response, "Accepted deals")

        stats = accepted_deals([dt.date(2020, 1, 1), dt.date(2099, 1, 1)])
        self.assertEqual(
            stats["by_valuetype"],
            [
                {"type": vt2, "target": None, "sum": Decimal("400")},
                {"type": vt1, "target": None, "sum": Decimal("200")},
            ],
        )
        self.assertEqual(len(stats["by_user"]), 1)
        self.assertEqual(stats["count"], 1)
        self.assertEqual(stats["sum"], Decimal("600"))

        stats = accepted_deals([dt.date(2020, 1, 1), dt.date(2099, 1, 1)], users=[])
        self.assertEqual(stats["sum"], Decimal("0"))
