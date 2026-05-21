export const getMasterOptionTagQuery = `
  query getMasterOptionTag($master_option_tag_id: Int, $limit: Int, $offset: Int) {
    getMasterOptionTag(master_option_tag_id: $master_option_tag_id, limit: $limit, offset: $offset) {
      id
      title
      status
    }
  }
`;

export const getOptionGroupQuery = `
  query getOptionGroup($prod_add_opt_group_id: Int, $use_for: String, $limit: Int, $offset: Int) {
    getOptionGroup(prod_add_opt_group_id: $prod_add_opt_group_id, use_for: $use_for, limit: $limit, offset: $offset) {
      prod_add_opt_group_id
      prod_add_opt_group_name
      use_for
      status
    }
  }
`;

export const getCustomFormulaQuery = `
  query getCustomFormula($formula_id: Int, $limit: Int, $offset: Int) {
    getCustomFormula(formula_id: $formula_id, limit: $limit, offset: $offset) {
      formula_id
      formula_name
      formula_value
      status
    }
  }
`;

export const getMasterOptionRangeQuery = `
  query getMasterOptionRange($range_id: Int, $option_id: Int, $limit: Int, $offset: Int) {
    getMasterOptionRange(range_id: $range_id, option_id: $option_id, limit: $limit, offset: $offset) {
      range_id
      option_id
      range_from
      range_to
      status
    }
  }
`;

export const getProductAdditionalOptionsQuery = `
  query product_additional_options($product_id: Int!, $limit: Int, $offset: Int) {
    product_additional_options(product_id: $product_id, limit: $limit, offset: $offset) {
      prod_add_opt_id
      prod_add_opt_name
      prod_add_opt_type
    }
  }
`;
