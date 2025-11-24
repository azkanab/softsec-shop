import 'bootstrap';
import 'lazysizes';
import SVGInjector from 'svg-injector-2';

import './components/navbar';
import './components/mycart';
import './components/sorter';
// import './components/product-filters';
import './components/address-form';
import './components/shipping-label-modal';
import './components/styleguide';
import './components/cart';
import './components/variant-choose';
import './components/paypal-button';

import '../scss/storefront.scss';

new SVGInjector().inject(document.querySelectorAll('svg[data-src]'));
