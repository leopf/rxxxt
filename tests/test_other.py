import unittest

from rxxxt import css_extend

class TestOther(unittest.TestCase):
  def test_css_extend(self):
    self.assertEqual(css_extend({}, class_attr="hello", style_attr="font-size: 10px;"), {
      "class": "hello",
      "style": "font-size: 10px;"
    })

    self.assertEqual(css_extend({ "class": "world", "style": "color:green" }, class_attr="hello", style_attr="font-size: 10px;"), {
      "class": "world hello",
      "style": "color:green;font-size: 10px;"
    })

if __name__ == "__main__":
  _ = unittest.main()
