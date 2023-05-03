import unittest
# import DPCLparser.DPCLAst as DPCLAst
# import DPCLparser.DPCLparser as DPCLparser
from ASTtools import DPCLAst, DPCLparser

class TestAutoID(unittest.TestCase):
    def setUp(self) -> None:
        schema = DPCLparser.load_schema('DPCLschema.json')
        success, data = DPCLparser.load_validate_json('examples/demand_payment.json', schema)
        assert success

        self.payment_program = DPCLAst.Program.from_json(data)

    def test_all_have_ID(self):
        self.assertTrue(all(len(obj.id) > 0) for obj in self.payment_program.globals)

    def test_IDs_unique(self):
        ids = [obj.id for obj in self.payment_program.globals]
        self.assertEqual(len(ids), len(set(ids)))

    def test_ID_order(self):
        self.assertEqual(self.payment_program.globals[0].id, '_DF0')
        self.assertEqual(self.payment_program.globals[1].id, '_PF0')
        self.assertEqual(self.payment_program.globals[2].id, '_RR0')
        self.assertEqual(self.payment_program.globals[3].id, '_RR1')


class TestNamespace(unittest.TestCase):
    def setUp(self) -> None:
        schema = DPCLparser.load_schema('DPCLschema.json')
        success, data = DPCLparser.load_validate_json('examples/demand_payment.json', schema)
        assert success

        self.payment_program = DPCLAst.Program.from_json(data)

    def test_get(self):
        self.assertNotEqual(self.payment_program.namespace.get('_RR0'), None)
        self.assertNotEqual(self.payment_program.namespace.get('pay_duty'), None)

    def test_get_nonglobal(self):
        self.assertNotEqual(self.payment_program.namespace.get('apologize'), None)


if __name__ == '__main__':
    unittest.main()
