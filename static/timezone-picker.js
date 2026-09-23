import "./vendor/tom-select-2.6.2/tom-select.base.min.js";

// Tom Select owns search, keyboard navigation, and ARIA. Django still validates the
// native select's submitted IANA value; our adapter supplies labels and country keywords.
export function enhanceTimezoneSelect(select, searchData = {}) {
  for (const option of select.options) {
    option.dataset.country = searchData[option.value] || "";
    option.dataset.searchableValue = option.value.replaceAll("_", " ").replaceAll("/", " ");
  }
  const picker = new window.TomSelect(select, {
    maxItems: 1,
    maxOptions: null,
    create: false,
    allowEmptyOption: !select.required,
    hideSelected: false,
    closeAfterSelect: true,
    placeholder: "Search city, country, region, or timezone",
    searchField: ["text", "value", "country", "searchableValue"],
    sortField: [{ field: "$order" }, { field: "$score" }],
    lockOptgroupOrder: true,
    onDelete: () => false, // Change to another valid choice; never clear to arbitrary text.
    render: {
      option(data) {
        const option = document.createElement("div");
        const label = document.createElement("span");
        label.textContent = data.text.split(" · ")[0];
        option.append(label);
        if (data.value) {
          const id = document.createElement("code");
          id.textContent = data.value;
          option.append(id);
        }
        return option;
      },
    },
    onDropdownOpen() {
      if (!this.control_input.value) this.dropdown_content.scrollTop = 0;
    },
  });
  select.setAttribute("aria-hidden", "true"); // Only the enhanced combobox is announced.
  // Typing a search does not edit a preference. Selection still emits native change events.
  picker.control_input.addEventListener("input", event => event.stopPropagation());
  // Detection temporarily disables the underlying simulator select while posting.
  new MutationObserver(() => {
    if (select.disabled !== picker.isDisabled) {
      if (select.disabled) picker.disable();
      else picker.enable();
    }
  }).observe(select, { attributes: true, attributeFilter: ["disabled"] });
  return picker;
}
