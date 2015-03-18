from django.test import TestCase

from staffing.forms import KeyboardTimesheetField


class KeyboardTimesheetFieldTest(TestCase):
    def test_prepare_value(self):
        data = (
            # This value is how the percent representing 0:15 is stored in the
            # DB on the staging server
            (0.0357142857142857, '0:15'),
        )
        field = KeyboardTimesheetField()
        field.day_duration = 7.0
        for percent, expected in data:
            output = field.prepare_value(percent)
            self.assertEquals(output, expected)

    def test_convert_round_trip(self):
        data = ('0:15', '1:01', '2:30', '0:01', '8:00')
        field = KeyboardTimesheetField()
        field.day_duration = 7.0
        for input_str in data:
            percent = field.to_python(input_str)
            output_str = field.prepare_value(percent)
            self.assertEquals(output_str, input_str)
