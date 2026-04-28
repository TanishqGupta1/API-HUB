"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getProductAdditionalOptionsQuery = exports.getMasterOptionRangeQuery = exports.getCustomFormulaQuery = exports.getOptionGroupQuery = exports.getMasterOptionTagQuery = void 0;
exports.getMasterOptionTagQuery = `
  query getMasterOptionTag($master_option_tag_id: Int, $limit: Int, $offset: Int) {
    getMasterOptionTag(master_option_tag_id: $master_option_tag_id, limit: $limit, offset: $offset) {
      id
      title
      status
    }
  }
`;
exports.getOptionGroupQuery = `
  query getOptionGroup($prod_add_opt_group_id: Int, $use_for: String, $limit: Int, $offset: Int) {
    getOptionGroup(prod_add_opt_group_id: $prod_add_opt_group_id, use_for: $use_for, limit: $limit, offset: $offset) {
      prod_add_opt_group_id
      prod_add_opt_group_name
      use_for
      status
    }
  }
`;
exports.getCustomFormulaQuery = `
  query getCustomFormula($formula_id: Int, $limit: Int, $offset: Int) {
    getCustomFormula(formula_id: $formula_id, limit: $limit, offset: $offset) {
      formula_id
      formula_name
      formula_value
      status
    }
  }
`;
exports.getMasterOptionRangeQuery = `
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
exports.getProductAdditionalOptionsQuery = `
  query product_additional_options($product_id: Int!, $limit: Int, $offset: Int) {
    product_additional_options(product_id: $product_id, limit: $limit, offset: $offset) {
      prod_add_opt_id
      prod_add_opt_name
      prod_add_opt_type
    }
  }
`;
