from django.test import TestCase, Client
from django.db.models import Max
import pytest

from .models import Airport, Flight, Passenger

# Marking the whole file should we write non-TestCase functions later
pytestmark = pytest.mark.django_db

# Create your tests here.
class FlightTestCase(TestCase):

    def setUp(self):

        # create airports
        self.a1 = Airport.objects.create(code="AAA", city="City A")
        self.a2 = Airport.objects.create(code="BBB", city="City B")
        self.a3 = Airport.objects.create(code="CCC", city="City C")

        # valid
        self.f1 = Flight.objects.create(origin=self.a1, destination=self.a2, duration=8)
        self.f2 = Flight.objects.create(origin=self.a1, destination=self.a3, duration=5)
        self.f3 = Flight.objects.create(origin=self.a2, destination=self.a3, duration=3)

        # invalid
        self.f4 = Flight.objects.create(origin=self.a1, destination=self.a2, duration=-100)
        self.f5 = Flight.objects.create(origin=self.a1, destination=self.a1, duration=3)


    def test_departures_count(self):
        a = Airport.objects.get(code="AAA")
        self.assertEqual(a.departures.count(),4)

    def test_arrivals_count(self):
        a = Airport.objects.get(code="BBB")
        self.assertEqual(a.arrivals.count(),2)

    def test_valid_flight(self):
        a1 = Airport.objects.get(code="AAA")
        a2 = Airport.objects.get(code="BBB")
        f = Flight.objects.get(origin=a1,destination=a2,duration=8)
        self.assertTrue(f.is_valid_flight())

    def test_invalid_flight_destination(self):
        a1 = Airport.objects.get(code="AAA")
        f = Flight.objects.get(origin=a1, destination=a1)
        self.assertFalse(f.is_valid_flight())

    def test_invalid_flight_duration(self):
        a1 = Airport.objects.get(code="AAA")
        a2 = Airport.objects.get(code="BBB")
        f = Flight.objects.get(origin=a1, destination=a2, duration=-100)
        self.assertFalse(f.is_valid_flight())

    def test_index(self):
        c = Client()
        response = c.get("/flights/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["flights"].count(), 5)

    def test_valid_flight_page(self):
        a1 = Airport.objects.get(code="AAA")
        f = Flight.objects.get(origin=a1, destination=a1)

        c = Client()
        response = c.get(f"/flights/{f.id}")
        self.assertEqual(response.status_code, 200)


    # capture invalid flight
    def test_invalid_flight_page(self):
        max_id = (Flight.objects.aggregate(Max("id"))["id__max"]) + 1

        c = Client()
        response = c.get(f"/flights/{max_id}/")
        self.assertEqual(response.status_code, 404)
    
    def test_flight_page_passengers(self):
        # create passenger
        p1 = Passenger.objects.create(first="Alice", last="Adams")
        p2 = Passenger.objects.create(first="Alice", last="Adams")


        # add to existing flight f1
        self.f1.passengers.add(p1)
        self.f1.passengers.add(p2)


        c = Client()
        response = c.get(f"/flights/{self.f1.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["passengers"].count(),2)

    def test_flight_page_non_passengers(self):
        # nott added to flight
        p1 = Passenger.objects.create(first="Alice",last="Adams")
        p2 = Passenger.objects.create(first="Harry",last="Potter")


        c = Client()
        response = c.get(f"/flights/{self.f2.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["non_passengers"].count(), 2)

