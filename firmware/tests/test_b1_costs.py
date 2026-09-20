from hardware.tools.costs import calculate


def test_unknown_cost_is_not_free_or_a_complete_total():
    bom = {'date': '2026-09-20', 'rows': [
        {'line_id': 'TC:U1', 'per_kit': 6, 'unit_usd': 2},
        {'line_id': 'ALL:case', 'per_kit': 1, 'unit_usd': None},
    ]}
    result = calculate(bom)
    assert result['known_kit_subtotal_usd'] == 12
    assert result['procurement_kit_usd'] is None
    assert result['five_year_tco_usd'] is None and result['payback_years'] is None
    assert result['tc_replacement_cells_per_kit'] == 12
    # Even a complete parts list does not establish installation or benefits.
    bom['rows'][1]['unit_usd'] = 5
    result = calculate(bom)
    assert result['procurement_kit_usd'] == 17
    assert result['complete_installed_kit_usd'] is None
    assert result['payback_years'] is None
