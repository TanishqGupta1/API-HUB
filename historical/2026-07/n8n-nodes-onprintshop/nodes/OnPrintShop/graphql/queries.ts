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

export const getProductCategoryQuery = `
  query productCategory($category_id: Int, $limit: Int, $offset: Int) {
    productCategory(category_id: $category_id, limit: $limit, offset: $offset) {
      productCategory {
        category_id
        sort_order
        status
        parent_id
        category_name
        category_url
        category_internal_name
        category_image
        short_description
        category_header_content
        long_description
        seo_page_title
        seo_page_description
        external_ref
      }
      totalProductCategorySize
      currentCount
    }
  }
`;

export const getProductStocksQuery = `
  query productStocks($product_id: Int!, $limit: Int, $offset: Int) {
    productStocks(product_id: $product_id, limit: $limit, offset: $offset) {
      productStocks {
        stock_id
        product_id
        product_name
        size_id
        size_title
        credit_stock
        debited_stock
        stock_quantity
        option_details
      }
      totalProductStocks
      currentCount
    }
  }
`;

export const getProductsListQuery = `
  query products($products_id: Int, $limit: Int, $offset: Int) {
    products(products_id: $products_id, limit: $limit, offset: $offset) {
      products {
        product_id
        product_name
        main_sku
        isstock
        external_ref
      }
      totalProducts
      currentCount
    }
  }
`;

export const getProductsDetailsQuery = `
  query productsDetails(
    $products_id: Int
    $limit: Int
    $offset: Int
    $status: Int
    $all_store: Int
    $external_catalogue: Int
  ) {
    productsDetails(
      products_id: $products_id
      limit: $limit
      offset: $offset
      status: $status
      all_store: $all_store
      external_catalogue: $external_catalogue
    ) {
      products {
        product_id
        product_name
        main_sku
        external_ref
        status
        default_category_id
        product_type
        price_defining_method
        product_size {
          size_id
          size_title
          size_width
          size_height
          default_size
        }
        product_additional_options {
          prod_add_opt_id
          title
          options_type
          option_key
          master_option_id
        }
      }
      totalProducts
      currentCount
    }
  }
`;

export const getProductSkuMatrixQuery = `
  query getProductSkuMatrix($products_id: Int!, $prod_add_opt_ids: String) {
    getProductSkuMatrix(products_id: $products_id, prod_add_opt_ids: $prod_add_opt_ids) {
      matrix {
        size_id
        prod_add_opt_ids
        attribute_ids
      }
      totalRecords
    }
  }
`;
