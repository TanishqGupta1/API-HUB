"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.setMasterOptionAttributePriceMutation = exports.setMasterOptionAttributesMutation = exports.setMasterOptionTagMutation = exports.setOptionGroupMutation = exports.setCustomFormulaMutation = exports.setProductOptionRulesMutation = exports.setAssignOptionsMutation = exports.setProductDesignMutation = exports.setProductCategoryMutation = exports.setProductPagesMutation = exports.setProductSizeMutation = exports.setProductPriceMutation = exports.setProductMutation = void 0;
exports.setProductMutation = `
  mutation setProduct($input: ProductInput!) {
    setProduct(input: $input) {
      id
      title
      status
    }
  }
`;
exports.setProductPriceMutation = `
  mutation setProductPrice($input: ProductPriceInput!) {
    setProductPrice(input: $input) {
      status
      message
    }
  }
`;
exports.setProductSizeMutation = `
  mutation setProductSize($input: ProductSizeInput!) {
    setProductSize(input: $input) {
      status
      message
    }
  }
`;
exports.setProductPagesMutation = `
  mutation setProductPages($input: ProductPagesInput!) {
    setProductPages(input: $input) {
      status
      message
    }
  }
`;
exports.setProductCategoryMutation = `
  mutation setProductCategory($input: ProductCategoryInput!) {
    setProductCategory(input: $input) {
      status
      message
    }
  }
`;
exports.setProductDesignMutation = `
  mutation setProductDesign($input: ProductDesignInput!) {
    setProductDesign(input: $input) {
      status
      message
    }
  }
`;
exports.setAssignOptionsMutation = `
  mutation setAssignOptions($input: AssignOptionsInput!) {
    setAssignOptions(input: $input) {
      status
      message
    }
  }
`;
exports.setProductOptionRulesMutation = `
  mutation setProductOptionRules($input: ProductOptionRulesInput!) {
    setProductOptionRules(input: $input) {
      status
      message
    }
  }
`;
exports.setCustomFormulaMutation = `
  mutation setCustomFormula($input: CustomFormulaInput!) {
    setCustomFormula(input: $input) {
      status
      message
    }
  }
`;
exports.setOptionGroupMutation = `
  mutation setOptionGroup($input: OptionGroupInput!) {
    setOptionGroup(input: $input) {
      status
      message
    }
  }
`;
exports.setMasterOptionTagMutation = `
  mutation setMasterOptionTag($input: MasterOptionTagInput!) {
    setMasterOptionTag(input: $input) {
      status
      message
    }
  }
`;
exports.setMasterOptionAttributesMutation = `
  mutation setMasterOptionAttributes($input: MasterOptionAttributesInput!) {
    setMasterOptionAttributes(input: $input) {
      status
      message
    }
  }
`;
exports.setMasterOptionAttributePriceMutation = `
  mutation setMasterOptionAttributePrice($input: MasterOptionAttributePriceInput!) {
    setMasterOptionAttributePrice(input: $input) {
      status
      message
    }
  }
`;
