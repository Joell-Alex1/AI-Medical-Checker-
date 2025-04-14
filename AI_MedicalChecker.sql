create database MedicineAPI;

use MedicineAPI;
drop database medicineapi;

-- select * from medicine_info;

select * from aqi;
select * from allergy;
select * from symptom_causes;

CREATE TABLE aqi (
    min_aqi FLOAT NOT NULL,
    max_aqi FLOAT NOT NULL,
    message TEXT NOT NULL
);
select * from warning;
select * from medicine;
select * from purpose;


INSERT INTO aqi (min_aqi, max_aqi, message) VALUES
(0, 50, 'Good: Air quality is excellent. Enjoy outdoor activities.'),
(51, 100, 'Moderate: Air is acceptable but may be a concern for sensitive individuals.'),
(101, 150, 'Unhealthy for Sensitive Groups: Children, elderly, and those with respiratory issues should limit outdoor exposure.'),
(151, 200, 'Unhealthy: Everyone may experience health effects. Reduce outdoor activity, especially for sensitive groups.'),
(201, 300, 'Very Unhealthy: Health alert. Everyone should avoid outdoor exertion.'),
(301, 500, 'Hazardous: Serious health risk. Stay indoors and use air purifiers.');
select * from aqi;
