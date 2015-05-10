from django.test import TestCase

from staffing import utils


class TimeStringConversionTest(TestCase):
    def test_prepare_value(self):
        data = (
            # This value is how the percent representing 0:15 is stored in the
            # DB on the staging server
            (0.0357142857142857, '0:15'),
        )
        for percent, expected in data:
            output = utils.time_string_for_day_percent(percent, day_duration=7)
            self.assertEquals(output, expected)

    def test_convert_round_trip(self):
        data = ('0:15', '1:01', '2:30', '0:01', '8:00')
        day_duration = 7
        for input_str in data:
            percent = utils.day_percent_for_time_string(input_str, day_duration)
            output_str = utils.time_string_for_day_percent(percent, day_duration)
            self.assertEquals(output_str, input_str)
