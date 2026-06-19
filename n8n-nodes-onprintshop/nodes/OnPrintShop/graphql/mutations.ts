export const setProductMutation = `
  mutation setProduct($input: ProductInput!) {
    setProduct(input: $input) {
      id
      title
      status
    }
  }
`;

export const setProductPriceMutation = `
  mutation setProductPrice($input: ProductPriceInput!) {
    setProductPrice(input: $input) {
      status
      message
    }
  }
`;

export const setProductSizeMutation = `
  mutation setProductSize($input: ProductSizeInput!) {
    setProductSize(input: $input) {
      status
      message
    }
  }
`;

export const setProductPagesMutation = `
  mutation setProductPages($input: ProductPagesInput!) {
    setProductPages(input: $input) {
      status
      message
    }
  }
`;

export const setProductCategoryMutation = `
  mutation setProductCategory($input: ProductCategoryInput!) {
    setProductCategory(input: $input) {
      status
      message
    }
  }
`;

export const setProductDesignMutation = `
  mutation setProductDesign($input: ProductDesignInput!) {
    setProductDesign(input: $input) {
      status
      message
    }
  }
`;

export const setAssignOptionsMutation = `
  mutation setAssignOptions($input: AssignOptionsInput!) {
    setAssignOptions(input: $input) {
      status
      message
    }
  }
`;

export const setProductOptionRulesMutation = `
  mutation setProductOptionRules($input: ProductOptionRulesInput!) {
    setProductOptionRules(input: $input) {
      status
      message
    }
  }
`;

export const setCustomFormulaMutation = `
  mutation setCustomFormula($input: CustomFormulaInput!) {
    setCustomFormula(input: $input) {
      status
      message
    }
  }
`;

export const setOptionGroupMutation = `
  mutation setOptionGroup($input: OptionGroupInput!) {
    setOptionGroup(input: $input) {
      status
      message
    }
  }
`;

export const setMasterOptionTagMutation = `
  mutation setMasterOptionTag($input: MasterOptionTagInput!) {
    setMasterOptionTag(input: $input) {
      status
      message
    }
  }
`;

export const setMasterOptionAttributesMutation = `
  mutation setMasterOptionAttributes($input: MasterOptionAttributesInput!) {
    setMasterOptionAttributes(input: $input) {
      status
      message
    }
  }
`;

export const setMasterOptionAttributePriceMutation = `
  mutation setMasterOptionAttributePrice($input: MasterOptionAttributePriceInput!) {
    setMasterOptionAttributePrice(input: $input) {
      status
      message
    }
  }
`;
