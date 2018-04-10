function countOccurences(aString, substring) {
    var count = 0;
    var position = aString.indexOf(substring);
    while (position > -1) {
        ++count;
        position = aString.indexOf(substring, ++position);
    }
    return count;
}