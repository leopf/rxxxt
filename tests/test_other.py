import unittest
from rxxxt import add_attributes

class TestOther(unittest.TestCase):
  def test_css_extend(self):
    self.assertEqual(add_attributes({}, _class="hello", style="font-size: 10px;"), {
      "class": "hello",
      "style": "font-size: 10px;"
    })

    self.assertEqual(add_attributes({ "class": "world", "style": "color:green" }, _class="hello", style="font-size: 10px;"), {
      "class": "hello world",
      "style": "font-size: 10px;;color:green"
    })

if __name__ == "__main__":
  _ = unittest.main()
