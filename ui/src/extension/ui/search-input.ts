import searchIcon from '../../assets/icons/search.svg?raw';

export function initSearchInput(selector: string) {
  const searchContainer = gradioApp().querySelector<HTMLDivElement>(selector);
  if (searchContainer == null) {
    throw new Error(`Search container '${selector}' not found.`);
  }
  const searchInput = searchContainer.getElementsByTagName('input')[0];
  if (searchInput == null) {
    throw new Error('Search input not found.');
  }
  searchInput.classList.add('ts-search-input');

  const searchIconContainer = document.createElement('div');
  searchIconContainer.className = 'ts-search-icon';
  searchIconContainer.innerHTML = searchIcon;
  searchInput.parentElement!.appendChild(searchIconContainer);

  return searchInput;
}

// function initImport(selector: string) {
//   const importContainer = gradioApp().querySelector<HTMLDivElement>(selector);
//   if (importContainer == null) {
//     throw new Error(`Import container '${selector}' not found.`);
//   }
//   const importInput = importContainer.getElementsByTagName('input')[0];
//   if (importInput == null) {
//     throw new Error('Import input not found.');
//   }
//   return importInput;
// }
