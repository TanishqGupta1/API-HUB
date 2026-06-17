export const setProductMutation = `
  mutation setProduct($inputs: [ProductInput!]!) {
    setProduct(inputs: $inputs) {
      result
      message
      id
    }
  }
`;

export const setProductPriceMutation = `
  mutation setProductPrice($inputs: [ProductPriceInput!]!) {
    setProductPrice(inputs: $inputs) {
      result
      message
      id
    }
  }
`;

export const setProductSizeMutation = `
  mutation setProductSize($inputs: [ProductSizeInput!]!) {
    setProductSize(inputs: $inputs) {
      result
      message
      id
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
  mutation setProductCategory($inputs: [ProductCategoryInput!]!) {
    setProductCategory(inputs: $inputs) {
      result
      message
      id
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
  mutation setAssignOptions($inputs: [AssignOptionsInput!]!) {
    setAssignOptions(inputs: $inputs) {
      result
      message
      id
    }
  }
`;

export const setProductSkuMutation = `
  mutation setProductSku($inputs: [ProductSkuInput!]!) {
    setProductSku(inputs: $inputs) {
      index
      result
      message
      id
    }
  }
`;

export const updateProductStockMutation = `
  mutation updateProductStock(
    $stock_id: Int
    $product_sku: String
    $action: UpdateProductStockActionEnum!
    $input: UpdateProductStockInput!
  ) {
    updateProductStock(
      stock_id: $stock_id
      product_sku: $product_sku
      action: $action
      input: $input
    ) {
      result
      message
      id
      stock_quantity
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
